import os
import uuid
import csv
from django.contrib import messages
from datetime import date
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse

from .forms_import import ImportGestaoPessoasForm
from testes.management.commands.import_gestao_pessoas import run_import  # ajuste o import conforme seu caminho

from dal import autocomplete

from .forms import TestePromocaoForm, UsuarioCreateForm, UsuarioUpdateForm, UsuarioResetSenhaForm
from .models import (
    AuditLog,
    Colaborador,
    Funcao,
    Loja,
    PremioPago,
    Solicitante,
    TesteControlePeriodo,
    TestePromocao,
)

User = get_user_model()

# =========================
# Autocompletes (DAL / Select2)
# =========================
class ColaboradorAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Colaborador.objects.filter(ativo=True).select_related("loja")

        loja_id = self.forwarded.get("loja", None)
        if loja_id:
            qs = qs.filter(loja_id=loja_id)

        if self.q:
            qs = qs.filter(nome__icontains=self.q)

        return qs

    def get_result_label(self, item):
        return f"{item.nome} • RE {item.re}"

    def get_selected_result_label(self, item):
        return item.nome

class LojaAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Loja.objects.filter(ativo=True)
        if self.q:
            qs = qs.filter(nome__icontains=self.q)
        return qs


class SolicitanteAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Solicitante.objects.all()
        if self.q:
            qs = qs.filter(nome__icontains=self.q)
        return qs


class FuncaoAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Funcao.objects.all()
        if self.q:
            qs = qs.filter(nome__icontains=self.q)
        return qs


@login_required
def api_lojas(request):
    q = (request.GET.get("q") or "").strip()
    qs = Loja.objects.filter(ativo=True)
    if q:
        qs = qs.filter(nome__icontains=q)

    data = [{"id": str(loja.id), "text": loja.nome} for loja in qs.order_by("nome")[:30]]
    return JsonResponse({"results": data})


@login_required
def api_colaboradores(request):
    q = (request.GET.get("q") or "").strip()
    loja_id = (request.GET.get("loja_id") or "").strip()
    funcao_id = (request.GET.get("funcao_id") or "").strip()

    qs = Colaborador.objects.filter(ativo=True)
    if loja_id.isdigit():
        qs = qs.filter(loja_id=int(loja_id))
    else:
        # Sem loja selecionada, nao retorna lista para evitar escolha invalida.
        return JsonResponse({"results": []})

    # Se a funcao-alvo do teste foi selecionada, oculta colaboradores que ja estao nessa funcao.
    if funcao_id.isdigit():
        qs = qs.exclude(funcao_id=int(funcao_id))

    if q:
        qs = qs.filter(nome__icontains=q)

    data = [
        {
            "id": str(c.id),
            "text": c.nome,
            "re": c.re,
            "funcao_id": c.funcao_id,
        }
        for c in qs.order_by("nome")[:30]
    ]
    return JsonResponse({"results": data})


@login_required
def api_solicitantes(request):
    q = (request.GET.get("q") or "").strip()
    qs = Solicitante.objects.all()
    if q:
        qs = qs.filter(nome__icontains=q)

    data = [{"id": str(s.id), "text": s.nome} for s in qs.order_by("nome")[:30]]
    return JsonResponse({"results": data})


@login_required
def api_funcoes(request):
    q = (request.GET.get("q") or "").strip()
    qs = Funcao.objects.all()
    if q:
        qs = qs.filter(nome__icontains=q)

    data = [{"id": str(f.id), "text": f.nome} for f in qs.order_by("nome")[:30]]
    return JsonResponse({"results": data})


@login_required
def api_loja_quadro(request, loja_id):
    loja = get_object_or_404(Loja.objects.select_related("regiao"), pk=loja_id)

    colabs_ativos_qs = Colaborador.objects.filter(loja=loja, ativo=True).select_related("funcao")
    ativos_total = colabs_ativos_qs.count()

    por_funcao_qs = (
        colabs_ativos_qs.values("funcao_id", "funcao__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "funcao__nome")
    )
    por_funcao = [
        {
            "funcao_id": row["funcao_id"],
            "funcao": row["funcao__nome"] or "Sem função",
            "total": row["total"],
        }
        for row in por_funcao_qs
    ]

    quadro = loja.quadro_contratado or 0
    return JsonResponse(
        {
            "loja": {"id": loja.id, "nome": loja.nome, "regiao": loja.regiao.nome},
            "quadro_contratado": quadro,
            "ativos_total": ativos_total,
            "diferenca_quadro": quadro - ativos_total,
            "por_funcao": por_funcao,
        }
    )


# =========================
# Helpers de request / fluxo
# =========================
def redirect_back_or_list(request, fallback_url_name="testes:lista"):
    ref = request.META.get("HTTP_REFERER")
    return redirect(ref) if ref else redirect(fallback_url_name)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _user_agent(request):
    return (request.META.get("HTTP_USER_AGENT") or "")[:255]


def _selected_ids(request):
    ids = request.POST.getlist("selected")
    cleaned = []
    for v in ids:
        try:
            cleaned.append(int(v))
        except ValueError:
            pass
    return cleaned


def _require_obs(request):
    obs = (request.POST.get("observacao") or "").strip()
    if not obs:
        return None
    return obs


def _premios_pagos_count(teste):
    annotated = getattr(teste, "premios_count", None)
    if annotated is not None:
        return annotated

    prefetched = getattr(teste, "_prefetched_objects_cache", {}).get("premios")
    if prefetched is not None:
        return len(prefetched)

    return teste.premios.count()


def _can_promote_teste(teste):
    return _premios_pagos_count(teste) >= 1


def _competencia_controle(ref_date=None):
    # Periodo 20-19: dias 20..fim do mes pertencem ao mes seguinte.
    ref = ref_date or timezone.localdate()
    if ref.day >= 20:
        if ref.month == 12:
            return date(ref.year + 1, 1, 1)
        return date(ref.year, ref.month + 1, 1)
    return date(ref.year, ref.month, 1)


def _periodo_controle_bounds(competencia):
    # competencia e o primeiro dia do mes "rotulo" do periodo.
    if competencia.month == 1:
        inicio = date(competencia.year - 1, 12, 20)
    else:
        inicio = date(competencia.year, competencia.month - 1, 20)
    fim = date(competencia.year, competencia.month, 19)
    return inicio, fim


def _get_or_create_controle_periodo(teste, competencia=None):
    comp = competencia or _competencia_controle()
    controle, _ = TesteControlePeriodo.objects.get_or_create(teste=teste, competencia=comp)
    return controle


def _controle_status_payload(controle, teste=None):
    if teste and teste.status != TestePromocao.Status.EM_ANDAMENTO and not controle:
        if teste.status == TestePromocao.Status.PROMOVER:
            return {"codigo": "FINALIZADO_PROMOVIDO", "label": "Promovido", "tone": "emerald"}
        if teste.status == TestePromocao.Status.CANCELAR:
            return {"codigo": "FINALIZADO_CANCELADO", "label": "Cancelado", "tone": "rose"}
        return {"codigo": "FINALIZADO", "label": "Finalizado", "tone": "slate"}

    if not controle:
        return {
            "codigo": "AGUARDANDO_QUESTIONAR",
            "label": "Aguardando questionar",
            "tone": "slate",
        }

    if controle.executado_em:
        return {"codigo": "CONCLUIDO", "label": "Concluído", "tone": "emerald"}
    if controle.decisao_supervisor:
        return {"codigo": "AGUARDANDO_EXECUCAO", "label": "Aguardando execução", "tone": "indigo"}
    if controle.questionado_em:
        return {"codigo": "AGUARDANDO_RESPOSTA", "label": "Aguardando resposta", "tone": "amber"}
    return {"codigo": "AGUARDANDO_QUESTIONAR", "label": "Aguardando questionar", "tone": "slate"}


def _marcar_execucao_controle(teste, user, observacao="", competencia=None):
    controle = _get_or_create_controle_periodo(teste, competencia=competencia)
    updates = []
    hoje = timezone.localdate()
    if controle.executado_em != hoje:
        controle.executado_em = hoje
        updates.append("executado_em")
    if controle.executado_por_id != getattr(user, "id", None):
        controle.executado_por = user
        updates.append("executado_por")
    if observacao and not controle.observacao:
        controle.observacao = observacao[:255]
        updates.append("observacao")
    if updates:
        controle.save(update_fields=updates + ["updated_at"])
    return controle


def _ja_pagou_premio_no_periodo(teste, competencia=None):
    comp = competencia or _competencia_controle()
    inicio, fim = _periodo_controle_bounds(comp)
    return teste.premios.filter(data_pagamento__range=(inicio, fim)).exists()


def _acoes_bloqueadas_por_pagamento_periodo(teste):
    # Se ja houve pagamento de premio no ciclo 20-19, qualquer nova acao operacional
    # (pagar/promover/cancelar) deve aguardar o proximo periodo.
    return _ja_pagou_premio_no_periodo(teste)


# =========================
# Tela principal (lista + filtros + KPIs)
# =========================
@login_required
def teste_list(request):
    q = (request.GET.get("q") or "").strip()
    re_ = (request.GET.get("re") or "").strip()
    solicitante_ids = request.GET.getlist("solicitante")
    status_list = request.GET.getlist("status")
    controle_list = request.GET.getlist("controle")
    controle_validos = {"AGUARDANDO_QUESTIONAR", "AGUARDANDO_RESPOSTA", "AGUARDANDO_EXECUCAO"}
    controle_list = [c for c in controle_list if c in controle_validos]

    sort = (request.GET.get("sort") or "").strip()         # ex: "premios"
    direction = (request.GET.get("dir") or "desc").strip() # "asc" ou "desc"
    if direction not in ("asc", "desc"):
        direction = "desc"

    testes = (
        TestePromocao.objects
        .select_related("loja", "loja__regiao", "solicitante", "funcao")
        .prefetch_related("premios")
        .all()
    )

    # filtros
    if q:
        testes = testes.filter(colaborador_nome__icontains=q)
    if re_:
        testes = testes.filter(colaborador_re__icontains=re_)
    if solicitante_ids:
        testes = testes.filter(solicitante_id__in=solicitante_ids)
    if status_list:
        testes = testes.filter(status__in=status_list)

    # anotação para ordenar por quantidade de prêmios pagos
    testes = testes.annotate(premios_count=Count("premios", distinct=True))

    # ordenação dinâmica
    order_map = {
        "premios": "premios_count",   # <- usa a anotação
        "inicio": "data_inicio",
        "status": "status",
        "re": "colaborador_re",
        "nome": "colaborador_nome",
        "funcao": "funcao__nome",
        "loja": "loja__nome",
        "regiao": "loja__regiao__nome",
        "solicitante": "solicitante__nome",
    }

    order_field = order_map.get(sort)

    if order_field:
        prefix = "" if direction == "asc" else "-"
        testes = testes.order_by(f"{prefix}{order_field}", "-id")
    else:
        # sua ordenação padrão antiga
        testes = testes.order_by("status", "-data_inicio")

    # Controle do periodo atual (20-19): monta status para uso na coluna e no filtro.
    competencia_atual = _competencia_controle()
    testes = list(testes)
    controles_map_lista = {
        c.teste_id: c
        for c in TesteControlePeriodo.objects.filter(
            teste_id__in=[t.id for t in testes],
            competencia=competencia_atual,
        ).select_related("executado_por")
    }
    for t in testes:
        controle = controles_map_lista.get(t.id)
        t.controle_periodo_atual = controle
        t.controle_periodo_status = _controle_status_payload(controle, teste=t)

    if controle_list:
        testes = [t for t in testes if t.controle_periodo_status["codigo"] in controle_list]

    total_resultados = len(testes)
    paginator = Paginator(testes, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    testes = page_obj

    periodo_inicio, periodo_fim = _periodo_controle_bounds(competencia_atual)

    params_sem_pagina = request.GET.copy()
    params_sem_pagina.pop("page", None)
    querystring_sem_pagina = params_sem_pagina.urlencode()

    inicio_pagina = max(1, page_obj.number - 2)
    fim_pagina = min(paginator.num_pages, page_obj.number + 2)
    paginas_visiveis = range(inicio_pagina, fim_pagina + 1)

    solicitantes = Solicitante.objects.order_by("nome")

    hoje = now().date()
    kpis = {
        "em_andamento": TestePromocao.objects.filter(status=TestePromocao.Status.EM_ANDAMENTO).count(),
        "promovidos_mes": TestePromocao.objects.filter(
            status=TestePromocao.Status.PROMOVER,
            data_promovido__month=hoje.month,
            data_promovido__year=hoje.year,
        ).count(),
        "cancelados_mes": TestePromocao.objects.filter(
            status=TestePromocao.Status.CANCELAR,
            data_cancelado__month=hoje.month,
            data_cancelado__year=hoje.year,
        ).count(),
        "premios_pagos_mes": PremioPago.objects.filter(
            data_pagamento__month=hoje.month,
            data_pagamento__year=hoje.year,
        ).count(),
    }

    context = {
        "testes": testes,
        "page_obj": page_obj,
        "is_paginated": page_obj.paginator.num_pages > 1,
        "paginas_visiveis": paginas_visiveis,
        "querystring_sem_pagina": querystring_sem_pagina,
        "solicitantes": solicitantes,
        "filtros": {
            "q": q,
            "re": re_,
            "solicitante": solicitante_ids,
            "status": status_list,
            "controle": controle_list,
        },
        "kpis": kpis,
        "total_resultados": total_resultados,
        "competencia_controle_atual": competencia_atual,
        "periodo_controle_inicio": periodo_inicio,
        "periodo_controle_fim": periodo_fim,
    }
    return render(request, "testes/teste_list.html", context)

# =========================
# Cadastro de novo teste
# =========================
@login_required
def teste_create(request):
    if request.method == "POST":
        form = TestePromocaoForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()

            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.CREATE_TESTE,
                teste=obj,
                ip=_client_ip(request),
                user_agent=_user_agent(request),
            )

            messages.success(request, "Teste cadastrado com sucesso!")
            return redirect("testes:lista")
    else:
        form = TestePromocaoForm()

    return render(request, "testes/teste_form.html", {"form": form})


# =========================
# Acoes individuais (drawer/lista)
# =========================
@login_required
@require_POST
def teste_acao(request, pk, acao):
    teste = get_object_or_404(TestePromocao, pk=pk)

    if teste.status != TestePromocao.Status.EM_ANDAMENTO:
        messages.error(request, "Este teste já está finalizado e não pode ser alterado.")
        return redirect_back_or_list(request)

    obs = _require_obs(request)
    if obs is None:
        messages.error(request, "Observação é obrigatória.")
        return redirect_back_or_list(request)

    if _acoes_bloqueadas_por_pagamento_periodo(teste):
        ini, fim = _periodo_controle_bounds(_competencia_controle())
        messages.error(
            request,
            f"Este teste já teve movimentação de prêmio no período atual ({ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}). Nova ação só no próximo período.",
        )
        return redirect_back_or_list(request)

    if acao == "promover":
        if not _can_promote_teste(teste):
            messages.error(request, "Não é possível promover sem pelo menos 1 prêmio pago.")
            return redirect_back_or_list(request)

        teste.status = TestePromocao.Status.PROMOVER
        teste.data_promovido = timezone.localdate()
        teste.data_cancelado = None
        teste.obs_promocao = obs
        teste.obs_cancelamento = ""
        teste.save(update_fields=["status", "data_promovido", "data_cancelado", "obs_promocao", "obs_cancelamento"])

        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.PROMOVER,
            teste=teste,
            note=obs,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
        _marcar_execucao_controle(teste, request.user, observacao=obs)

        messages.success(request, "Teste marcado como PROMOVIDO.")
        return redirect_back_or_list(request)

    if acao == "cancelar":
        teste.status = TestePromocao.Status.CANCELAR
        teste.data_cancelado = timezone.localdate()
        teste.data_promovido = None
        teste.obs_cancelamento = obs
        teste.obs_promocao = ""
        teste.save(update_fields=["status", "data_cancelado", "data_promovido", "obs_cancelamento", "obs_promocao"])

        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.CANCELAR,
            teste=teste,
            note=obs,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
        _marcar_execucao_controle(teste, request.user, observacao=obs)

        messages.success(request, "Teste marcado como CANCELADO.")
        return redirect_back_or_list(request)

    messages.error(request, "Ação inválida.")
    return redirect_back_or_list(request)


# =========================
# Drawer de detalhes (partial HTML)
# =========================
@login_required
def teste_detalhe(request, pk):
    t = get_object_or_404(
        TestePromocao.objects
        .select_related("funcao", "loja", "solicitante", "loja__regiao")
        .prefetch_related("premios"),
        pk=pk
    )
    pode_promover = (t.status == TestePromocao.Status.EM_ANDAMENTO) and _can_promote_teste(t)
    ativos_mesma_funcao_loja = None
    ativos_total_loja = Colaborador.objects.filter(loja=t.loja, ativo=True).count()
    if t.funcao_id:
        ativos_mesma_funcao_loja = Colaborador.objects.filter(
            loja=t.loja,
            ativo=True,
            funcao_id=t.funcao_id,
        ).count()
    competencia_atual = _competencia_controle()
    periodo_inicio, periodo_fim = _periodo_controle_bounds(competencia_atual)
    controle_periodo = TesteControlePeriodo.objects.filter(
        teste=t,
        competencia=competencia_atual,
    ).select_related("executado_por").first()
    controle_periodo_status = _controle_status_payload(controle_periodo, teste=t)
    premio_pago_no_periodo = t.premios.filter(data_pagamento__range=(periodo_inicio, periodo_fim)).exists()
    return render(
        request,
        "testes/partials/teste_detalhe_drawer.html",
        {
            "t": t,
            "pode_promover": pode_promover,
            "promocao_bloqueada": (t.status == TestePromocao.Status.EM_ANDAMENTO) and not pode_promover,
            "ativos_total_loja": ativos_total_loja,
            "ativos_mesma_funcao_loja": ativos_mesma_funcao_loja,
            "competencia_controle_atual": competencia_atual,
            "periodo_controle_inicio": periodo_inicio,
            "periodo_controle_fim": periodo_fim,
            "controle_periodo": controle_periodo,
            "controle_periodo_status": controle_periodo_status,
            "premio_pago_no_periodo": premio_pago_no_periodo,
            "decisoes_supervisor": TesteControlePeriodo.Decisao.choices,
        },
    )

# =========================
# Premio individual
# =========================
@login_required
@require_POST
@transaction.atomic
def teste_pagar_premio(request, pk):
    teste = get_object_or_404(TestePromocao, pk=pk)

    if teste.status != TestePromocao.Status.EM_ANDAMENTO:
        messages.error(request, "Este teste está finalizado (promovido/cancelado) e não pode receber prêmio.")
        return redirect_back_or_list(request)

    existentes = set(teste.premios.values_list("numero_premio", flat=True))
    proximo = next((n for n in (1, 2, 3) if n not in existentes), None)

    if proximo is None:
        messages.error(request, "Este teste já tem 3 prêmios pagos (limite atingido).")
        return redirect_back_or_list(request)

    if _ja_pagou_premio_no_periodo(teste):
        comp = _competencia_controle()
        ini, fim = _periodo_controle_bounds(comp)
        messages.error(
            request,
            f"Já existe prêmio pago neste período ({ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}).",
        )
        return redirect_back_or_list(request)

    obs = _require_obs(request)
    if obs is None:
        messages.error(request, "Observação é obrigatória para pagar prêmio.")
        return redirect_back_or_list(request)

    PremioPago.objects.create(
        teste=teste,
        numero_premio=proximo,
        data_pagamento=timezone.localdate(),
        observacao=obs,
    )

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.PAGAR_PREMIO,
        teste=teste,
        note=obs,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
    )
    _marcar_execucao_controle(teste, request.user, observacao=obs)

    messages.success(request, f"Prêmio {proximo} lançado com sucesso!")
    return redirect_back_or_list(request)


# -----------------------------
# AÇÕES EM LOTE (TODAS COM OBS OBRIGATÓRIA)
# -----------------------------
# =========================
# Acoes em lote (promover / cancelar / pagar)
# =========================
@login_required
@require_POST
@transaction.atomic
def testes_bulk_promover(request):
    ids = _selected_ids(request)
    if not ids:
        messages.error(request, "Selecione pelo menos 1 teste.")
        return redirect("testes:lista")

    obs = _require_obs(request)
    if obs is None:
        messages.error(request, "Observação é obrigatória.")
        return redirect("testes:lista")

    qs = (
        TestePromocao.objects
        .select_for_update()
        .annotate(premios_count=Count("premios", distinct=True))
        .filter(id__in=ids)
    )
    done, skipped_status, skipped_regra, skipped_periodo = 0, 0, 0, 0

    for t in qs:
        if t.status != TestePromocao.Status.EM_ANDAMENTO:
            skipped_status += 1
            continue

        if not _can_promote_teste(t):
            skipped_regra += 1
            continue

        if _acoes_bloqueadas_por_pagamento_periodo(t):
            skipped_periodo += 1
            continue

        t.status = TestePromocao.Status.PROMOVER
        t.data_promovido = timezone.localdate()
        t.data_cancelado = None
        t.obs_promocao = obs
        t.obs_cancelamento = ""
        t.save(update_fields=["status", "data_promovido", "data_cancelado", "obs_promocao", "obs_cancelamento"])

        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.PROMOVER,
            teste=t,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
            note=obs,
        )
        _marcar_execucao_controle(t, request.user, observacao=obs)

        done += 1

    if done:
        messages.success(request, f"{done} teste(s) promovido(s).")
    if skipped_status:
        messages.warning(request, f"{skipped_status} teste(s) ignorado(s) (não estavam em andamento).")
    if skipped_regra:
        messages.warning(request, f"{skipped_regra} teste(s) ignorado(s) (sem ao menos 1 prêmio pago).")
    if skipped_periodo:
        messages.warning(request, f"{skipped_periodo} teste(s) ignorado(s) (já tiveram pagamento no período atual).")

    return redirect("testes:lista")


@login_required
@require_POST
@transaction.atomic
def testes_bulk_cancelar(request):
    ids = _selected_ids(request)
    if not ids:
        messages.error(request, "Selecione pelo menos 1 teste.")
        return redirect("testes:lista")

    obs = _require_obs(request)
    if obs is None:
        messages.error(request, "Observação é obrigatória.")
        return redirect("testes:lista")

    qs = TestePromocao.objects.select_for_update().filter(id__in=ids)
    done, skipped, skipped_periodo = 0, 0, 0

    for t in qs:
        if t.status != TestePromocao.Status.EM_ANDAMENTO:
            skipped += 1
            continue

        if _acoes_bloqueadas_por_pagamento_periodo(t):
            skipped_periodo += 1
            continue

        t.status = TestePromocao.Status.CANCELAR
        t.data_cancelado = timezone.localdate()
        t.data_promovido = None
        t.obs_cancelamento = obs
        t.obs_promocao = ""
        t.save(update_fields=["status", "data_cancelado", "data_promovido", "obs_cancelamento", "obs_promocao"])

        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.CANCELAR,
            teste=t,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
            note=obs,
        )
        _marcar_execucao_controle(t, request.user, observacao=obs)

        done += 1

    if done:
        messages.success(request, f"{done} teste(s) cancelado(s).")
    if skipped:
        messages.warning(request, f"{skipped} teste(s) ignorado(s) (não estavam em andamento).")
    if skipped_periodo:
        messages.warning(request, f"{skipped_periodo} teste(s) ignorado(s) (já tiveram pagamento no período atual).")

    return redirect("testes:lista")


@login_required
@require_POST
@transaction.atomic
def testes_bulk_pagar(request):
    ids = _selected_ids(request)
    if not ids:
        messages.error(request, "Selecione pelo menos 1 teste.")
        return redirect("testes:lista")

    obs = _require_obs(request)
    if obs is None:
        messages.error(request, "Observação é obrigatória para pagar prêmio.")
        return redirect("testes:lista")

    qs = (
        TestePromocao.objects
        .select_for_update()
        .prefetch_related("premios")
        .filter(id__in=ids)
    )

    paid, skipped_status, skipped_limit, skipped_periodo = 0, 0, 0, 0

    for t in qs:
        if t.status != TestePromocao.Status.EM_ANDAMENTO:
            skipped_status += 1
            continue

        existentes = set(t.premios.values_list("numero_premio", flat=True))
        proximo = next((n for n in (1, 2, 3) if n not in existentes), None)

        if proximo is None:
            skipped_limit += 1
            continue

        if _ja_pagou_premio_no_periodo(t):
            skipped_periodo += 1
            continue

        PremioPago.objects.create(
            teste=t,
            numero_premio=proximo,
            data_pagamento=timezone.localdate(),
            observacao=obs,
        )

        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.PAGAR_PREMIO,
            teste=t,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
            note=obs,
        )
        _marcar_execucao_controle(t, request.user, observacao=obs)

        paid += 1

    if paid:
        messages.success(request, f"Prêmio lançado em {paid} teste(s).")
    if skipped_status:
        messages.warning(request, f"{skipped_status} ignorado(s) (não estavam em andamento).")
    if skipped_limit:
        messages.warning(request, f"{skipped_limit} ignorado(s) (já estão 3/3).")
    if skipped_periodo:
        messages.warning(request, f"{skipped_periodo} ignorado(s) (já receberam prêmio no período atual).")

    return redirect("testes:lista")


@login_required
@require_POST
@transaction.atomic
def testes_bulk_questionar(request):
    ids = _selected_ids(request)
    if not ids:
        messages.error(request, "Selecione pelo menos 1 teste.")
        return redirect("testes:lista")

    qs = TestePromocao.objects.select_for_update().filter(id__in=ids)
    done, skipped_status, skipped_ja = 0, 0, 0

    for t in qs:
        if t.status != TestePromocao.Status.EM_ANDAMENTO:
            skipped_status += 1
            continue

        controle = _get_or_create_controle_periodo(t)
        if controle.questionado_em:
            skipped_ja += 1
            continue

        controle.questionado_em = timezone.localdate()
        controle.save(update_fields=["questionado_em", "updated_at"])
        done += 1

    if done:
        messages.success(request, f"{done} teste(s) marcado(s) como questionado(s) no período atual.")
    if skipped_status:
        messages.warning(request, f"{skipped_status} ignorado(s) (não estavam em andamento).")
    if skipped_ja:
        messages.warning(request, f"{skipped_ja} ignorado(s) (já estavam questionados no período).")

    return redirect("testes:lista")


@login_required
@require_POST
@transaction.atomic
def teste_periodo_questionar(request, pk):
    teste = get_object_or_404(TestePromocao, pk=pk)
    controle = _get_or_create_controle_periodo(teste)

    if controle.questionado_em:
        messages.warning(request, "Este teste já foi marcado como questionado no período atual.")
        return redirect_back_or_list(request)

    updates = []
    hoje = timezone.localdate()
    if controle.questionado_em != hoje:
        controle.questionado_em = hoje
        updates.append("questionado_em")
    if updates:
        controle.save(update_fields=updates + ["updated_at"])

    messages.success(request, "Teste marcado como questionado no período atual.")
    return redirect_back_or_list(request)


@login_required
@require_POST
@transaction.atomic
def teste_periodo_decisao(request, pk):
    teste = get_object_or_404(TestePromocao, pk=pk)
    decisao = (request.POST.get("decisao_supervisor") or "").strip()
    observacao = (request.POST.get("observacao_periodo") or "").strip()

    escolhas_validas = {c[0] for c in TesteControlePeriodo.Decisao.choices}
    if decisao not in escolhas_validas:
        messages.error(request, "Selecione uma decisão válida do supervisor.")
        return redirect_back_or_list(request)

    controle = _get_or_create_controle_periodo(teste)
    if controle.decisao_supervisor or controle.respondido_em:
        messages.warning(request, "A decisão do supervisor deste período já foi registrada e não pode ser alterada.")
        return redirect_back_or_list(request)

    hoje = timezone.localdate()
    controle.decisao_supervisor = decisao
    controle.respondido_em = hoje
    if not controle.questionado_em:
        controle.questionado_em = hoje
    controle.observacao = observacao[:255]
    controle.save(
        update_fields=[
            "decisao_supervisor",
            "respondido_em",
            "questionado_em",
            "observacao",
            "updated_at",
        ]
    )

    messages.success(request, "Decisão do supervisor registrada no período atual.")
    return redirect_back_or_list(request)

# =========================
# Importacao de base (gestao de pessoas)
# =========================
def _is_staff(user):
    # Temporariamente tratamos importacao como recurso de admin da plataforma.
    return user.is_authenticated and user.is_superuser


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser


# =========================
# Admin interno - usuarios
# =========================
@login_required
@user_passes_test(_is_superuser)
def usuarios_list(request):
    q = (request.GET.get("q") or "").strip()
    perfil = (request.GET.get("perfil") or "").strip()
    status = (request.GET.get("status") or "").strip()

    usuarios = User.objects.all().order_by("username")

    if q:
        usuarios = usuarios.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    if perfil == "admin":
        usuarios = usuarios.filter(is_superuser=True)
    elif perfil == "usuario":
        usuarios = usuarios.filter(is_staff=False, is_superuser=False)

    if status == "ativo":
        usuarios = usuarios.filter(is_active=True)
    elif status == "inativo":
        usuarios = usuarios.filter(is_active=False)

    context = {
        "usuarios": usuarios,
        "filtros": {"q": q, "perfil": perfil, "status": status},
        "totais": {
            "todos": User.objects.count(),
            "ativos": User.objects.filter(is_active=True).count(),
            "admins": User.objects.filter(is_superuser=True).count(),
            "usuarios": User.objects.filter(is_superuser=False).count(),
        },
    }
    return render(request, "testes/usuarios_list.html", context)


@login_required
@user_passes_test(_is_superuser)
def usuario_create(request):
    if request.method == "POST":
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Usuário {user.username} criado com sucesso.")
            return redirect("testes:usuarios_lista")
    else:
        form = UsuarioCreateForm()

    return render(request, "testes/usuario_form.html", {"form": form})


@login_required
@user_passes_test(_is_superuser)
def usuario_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = UsuarioUpdateForm(request.POST, instance=user_obj)
        if form.is_valid():
            edited = form.save(commit=False)
            if user_obj.pk == request.user.pk and not edited.is_superuser:
                messages.error(request, "Você não pode remover o próprio perfil de Admin.")
            else:
                edited.save()
                messages.success(request, f"Usuário {edited.username} atualizado com sucesso.")
                return redirect("testes:usuarios_lista")
    else:
        form = UsuarioUpdateForm(instance=user_obj)

    return render(request, "testes/usuario_form.html", {"form": form, "usuario_edicao": user_obj})


@login_required
@user_passes_test(_is_superuser)
def usuario_reset_senha(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = UsuarioResetSenhaForm(request.POST)
        if form.is_valid():
            user_obj.set_password(form.cleaned_data["password1"])
            user_obj.save(update_fields=["password"])
            messages.success(request, f"Senha redefinida para {user_obj.username}.")
            return redirect("testes:usuarios_lista")
    else:
        form = UsuarioResetSenhaForm()

    return render(request, "testes/usuario_password_form.html", {"form": form, "usuario_alvo": user_obj})


@login_required
@user_passes_test(_is_superuser)
@require_POST
def usuario_toggle_ativo(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if user_obj.pk == request.user.pk and user_obj.is_active:
        messages.error(request, "Você não pode desativar o próprio usuário.")
        return redirect("testes:usuarios_lista")

    user_obj.is_active = not user_obj.is_active
    user_obj.save(update_fields=["is_active"])

    if user_obj.is_active:
        messages.success(request, f"Usuário {user_obj.username} ativado com sucesso.")
    else:
        messages.success(request, f"Usuário {user_obj.username} desativado com sucesso.")

    return redirect("testes:usuarios_lista")


@login_required
@user_passes_test(_is_staff)
@require_http_methods(["GET", "POST"])
def import_gestao_pessoas(request):
    """
    Etapa 1: upload -> preview (dry_run=True)
    Etapa 2: confirmar -> import real (dry_run=False)
    """
    if request.method == "GET":
        # limpa preview anterior se entrar de novo
        request.session.pop("import_gp_token", None)
        request.session.pop("import_gp_path", None)
        request.session.pop("import_gp_preview", None)
        return render(request, "testes/import_gestao_pessoas.html", {"form": ImportGestaoPessoasForm()})

    # POST: upload para preview
    form = ImportGestaoPessoasForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "testes/import_gestao_pessoas.html", {"form": form})

    f = form.cleaned_data["arquivo"]
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in [".xlsm", ".xlsx"]:
        form.add_error("arquivo", "Envie um arquivo .xlsm ou .xlsx")
        return render(request, "testes/import_gestao_pessoas.html", {"form": form})

    # salva arquivo temporário para poder confirmar depois
    imports_dir = os.path.join(settings.MEDIA_ROOT, "imports")
    os.makedirs(imports_dir, exist_ok=True)

    token = uuid.uuid4().hex
    filename = f"gestao_pessoas_{token}{ext}"
    full_path = os.path.join(imports_dir, filename)

    with open(full_path, "wb+") as dest:
        for chunk in f.chunks():
            dest.write(chunk)

    try:
        preview = run_import(full_path, dry_run=True)  # ✅ não grava
    except Exception as e:
        # se deu erro, remove arquivo
        try:
            os.remove(full_path)
        except OSError:
            pass
        messages.error(request, f"Erro ao gerar preview: {e}")
        return render(request, "testes/import_gestao_pessoas.html", {"form": ImportGestaoPessoasForm()})

    # guarda dados para a etapa de confirmação
    request.session["import_gp_token"] = token
    request.session["import_gp_path"] = full_path
    request.session["import_gp_preview"] = preview

    return render(
        request,
        "testes/import_gestao_pessoas.html",
        {
            "form": ImportGestaoPessoasForm(),
            "preview": preview,
            "token": token,
        },
    )


@login_required
@user_passes_test(_is_staff)
@require_http_methods(["POST"])
def import_gestao_pessoas_confirm(request):
    """
    Confirma o import real usando o arquivo salvo no preview.
    """
    token_form = request.POST.get("token", "")
    token_sess = request.session.get("import_gp_token")
    path = request.session.get("import_gp_path")

    if not token_sess or not path or token_form != token_sess:
        messages.error(request, "Preview expirou ou token inválido. Gere o preview novamente.")
        return redirect("testes:import_gestao_pessoas")

    if not os.path.exists(path):
        messages.error(request, "Arquivo do preview não encontrado. Gere o preview novamente.")
        return redirect("testes:import_gestao_pessoas")

    try:
        result = run_import(path, dry_run=False)  # ✅ grava de verdade
    except Exception as e:
        messages.error(request, f"Erro ao importar: {e}")
        return redirect("testes:import_gestao_pessoas")
    finally:
        # limpeza do arquivo e sessão
        try:
            os.remove(path)
        except OSError:
            pass
        request.session.pop("import_gp_token", None)
        request.session.pop("import_gp_path", None)
        request.session.pop("import_gp_preview", None)

    messages.success(request, "Importação concluída com sucesso!")
    # Se quiser, redireciona pra lista ou mantém na tela
    return render(request, "testes/import_gestao_pessoas_result.html", {"result": result})

# =========================
# Exportacao CSV (mesmos filtros da lista)
# =========================
@login_required
def teste_exportar(request):
    q = (request.GET.get("q") or "").strip()
    re_ = (request.GET.get("re") or "").strip()
    solicitante_ids = request.GET.getlist("solicitante")
    status_list = request.GET.getlist("status")

    sort = (request.GET.get("sort") or "").strip()
    direction = (request.GET.get("dir") or "desc").strip()
    if direction not in ("asc", "desc"):
        direction = "desc"

    testes = (
        TestePromocao.objects
        .select_related("loja", "loja__regiao", "solicitante", "funcao")
        .annotate(premios_count=Count("premios", distinct=True))
    )

    # aplicar mesmos filtros da lista
    if q:
        testes = testes.filter(colaborador_nome__icontains=q)
    if re_:
        testes = testes.filter(colaborador_re__icontains=re_)
    if solicitante_ids:
        testes = testes.filter(solicitante_id__in=solicitante_ids)
    if status_list:
        testes = testes.filter(status__in=status_list)

    # mesma ordenação
    order_map = {
        "premios": "premios_count",
        "inicio": "data_inicio",
        "status": "status",
        "re": "colaborador_re",
        "nome": "colaborador_nome",
        "funcao": "funcao__nome",
        "loja": "loja__nome",
        "regiao": "loja__regiao__nome",
        "solicitante": "solicitante__nome",
    }

    order_field = order_map.get(sort)

    if order_field:
        prefix = "" if direction == "asc" else "-"
        testes = testes.order_by(f"{prefix}{order_field}", "-id")
    else:
        testes = testes.order_by("status", "-data_inicio")

    # criar CSV
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="testes_exportados.csv"'

    # ✅ BOM para o Excel entender UTF-8 (acentos)
    response.write("\ufeff")

    # ✅ delimiter=';' para Excel PT-BR separar em colunas
    writer = csv.writer(response, delimiter=";")

    writer.writerow([
        "Nome",
        "RE",
        "Função",
        "Loja",
        "Região",
        "Status",
        "Prêmios pagos",
        "Data início",
    ])

    for t in testes:
        writer.writerow([
            t.colaborador_nome,
            t.colaborador_re,
            t.funcao.nome,
            t.loja.nome,
            t.loja.regiao.nome,
            t.get_status_display(),
            t.premios_count,
            t.data_inicio.strftime("%d/%m/%Y"),
        ])

    return response
