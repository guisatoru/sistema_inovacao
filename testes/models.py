from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE_TESTE = "CREATE_TESTE", "Criou teste"
        PAGAR_PREMIO = "PAGAR_PREMIO", "Pagou prêmio"
        PROMOVER = "PROMOVER", "Promoveu"
        CANCELAR = "CANCELAR", "Cancelou"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40, choices=Action.choices)
    teste = models.ForeignKey("TestePromocao", on_delete=models.CASCADE, related_name="logs")
    created_at = models.DateTimeField(auto_now_add=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    note = models.CharField(max_length=255, blank=True)  # observação

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de auditoria"
        verbose_name_plural = "Logs de auditoria"

    def __str__(self):
        return f"{self.get_action_display()} - {self.teste} - {self.user}"


class TesteControlePeriodo(models.Model):
    class Decisao(models.TextChoices):
        PAUSA = "PAUSA", "Pausa"
        PAGAR_PREMIO = "PAGAR_PREMIO", "Pagar prêmio"
        PROMOVER = "PROMOVER", "Promover"
        CANCELAR = "CANCELAR", "Cancelar"

    teste = models.ForeignKey("TestePromocao", on_delete=models.CASCADE, related_name="controles_periodo")
    competencia = models.DateField(help_text="Primeiro dia do mês de referência do ciclo 20-19.")

    questionado_em = models.DateField(null=True, blank=True)
    decisao_supervisor = models.CharField(max_length=20, choices=Decisao.choices, blank=True)
    respondido_em = models.DateField(null=True, blank=True)
    executado_em = models.DateField(null=True, blank=True)
    executado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="controles_periodo_executados",
    )
    observacao = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Controle mensal do teste"
        verbose_name_plural = "Controles mensais do teste"
        constraints = [
            models.UniqueConstraint(fields=["teste", "competencia"], name="uniq_controle_periodo_por_teste")
        ]
        ordering = ["-competencia", "-id"]

    def __str__(self):
        return f"{self.teste} - {self.competencia:%m/%Y}"


class Funcao(models.Model):
    nome = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Função"
        verbose_name_plural = "Funções"


class Regiao(models.Model):
    nome = models.CharField(max_length=80, unique=True)

    class Meta:
        verbose_name = "Região"
        verbose_name_plural = "Regiões"

    def __str__(self):
        return self.nome


class Loja(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    regiao = models.ForeignKey(Regiao, on_delete=models.PROTECT)
    quadro_contratado = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True, db_index=True)  # <- add db_index

    class Meta:
        verbose_name = "Loja"
        verbose_name_plural = "Lojas"

    def __str__(self):
        return self.nome

class Solicitante(models.Model):
    nome = models.CharField(max_length=120)

    def __str__(self):
        return self.nome
    
class Colaborador(models.Model):
    re = models.CharField(max_length=30, unique=True)
    nome = models.CharField(max_length=120)
    loja = models.ForeignKey(Loja, on_delete=models.PROTECT, related_name="colaboradores")
    funcao = models.ForeignKey(Funcao, on_delete=models.PROTECT, null=True, blank=True, related_name="colaboradores")
    ativo = models.BooleanField(default=True, db_index=True)  # <- add db_index

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores"
        indexes = [
            models.Index(fields=["loja", "ativo"]),
            models.Index(fields=["nome"]),
            # opcional: se você faz muito filtro por ativo sem loja
            # models.Index(fields=["ativo"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.re})"

class TestePromocao(models.Model):
    class Status(models.TextChoices):
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        PROMOVER = "PROMOVER", "Promovido"
        CANCELAR = "CANCELAR", "Cancelado"

    data_promovido = models.DateField(null=True, blank=True)
    data_cancelado = models.DateField(null=True, blank=True)

    # NOVO: observações das ações finais
    obs_promocao = models.CharField(max_length=255, blank=True)
    obs_cancelamento = models.CharField(max_length=255, blank=True)
    
    colaborador = models.ForeignKey(Colaborador, on_delete=models.PROTECT, null=True, blank=True, related_name="testes")

    class Meta:
        verbose_name = "Teste de promoção"
        verbose_name_plural = "Testes de promoção"

    colaborador_nome = models.CharField(max_length=120)
    colaborador_re = models.CharField(max_length=30)

    loja = models.ForeignKey(Loja, on_delete=models.PROTECT)
    solicitante = models.ForeignKey(Solicitante, on_delete=models.PROTECT)

    funcao = models.ForeignKey(Funcao, on_delete=models.PROTECT, related_name="testes", null=True, blank=True)
    data_inicio = models.DateField()

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EM_ANDAMENTO)

    observacoes = models.TextField(blank=True)
    anexo_folha_teste = models.FileField(upload_to="folhas_teste/", blank=True, null=True)

    @property
    def regiao(self):
        return self.loja.regiao

    @property
    def premios_pagos(self):
        return self.premios.count()

    def __str__(self):
        return f"{self.colaborador_nome} - {self.colaborador_re}"


class PremioPago(models.Model):
    teste = models.ForeignKey(TestePromocao, related_name="premios", on_delete=models.CASCADE)

    numero_premio = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )

    data_pagamento = models.DateField()

    # AGORA OBRIGATÓRIO
    observacao = models.CharField(max_length=255)

    class Meta:
        ordering = ["numero_premio"]
        constraints = [
            models.UniqueConstraint(
                fields=["teste", "numero_premio"],
                name="uniq_numero_premio_por_teste",
            )
        ]

    def __str__(self):
        return f"{self.teste} - Prêmio {self.numero_premio}"
