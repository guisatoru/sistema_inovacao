from django.urls import path
from . import views
from .views import LojaAutocomplete, SolicitanteAutocomplete, FuncaoAutocomplete, ColaboradorAutocomplete

app_name = "testes"

urlpatterns = [
    path("", views.teste_list, name="lista"),
    path("novo/", views.teste_create, name="novo"),

    # admin interno - usuarios
    path("usuarios/", views.usuarios_list, name="usuarios_lista"),
    path("usuarios/novo/", views.usuario_create, name="usuarios_novo"),
    path("usuarios/<int:pk>/editar/", views.usuario_edit, name="usuarios_editar"),
    path("usuarios/<int:pk>/senha/", views.usuario_reset_senha, name="usuarios_reset_senha"),
    path("usuarios/<int:pk>/toggle-ativo/", views.usuario_toggle_ativo, name="usuarios_toggle_ativo"),

    # ações individuais
    path("<int:pk>/pagar/", views.teste_pagar_premio, name="pagar"),
    path("<int:pk>/acao/<str:acao>/", views.teste_acao, name="acao"),
    path("<int:pk>/periodo/questionar/", views.teste_periodo_questionar, name="periodo_questionar"),
    path("<int:pk>/periodo/decisao/", views.teste_periodo_decisao, name="periodo_decisao"),

    # ações em lote
    path("bulk/pagar/", views.testes_bulk_pagar, name="bulk_pagar"),
    path("bulk/questionar/", views.testes_bulk_questionar, name="bulk_questionar"),
    path("bulk/promover/", views.testes_bulk_promover, name="bulk_promover"),
    path("bulk/cancelar/", views.testes_bulk_cancelar, name="bulk_cancelar"),

    # DAL autocompletes
    path("loja-autocomplete/", LojaAutocomplete.as_view(), name="loja-autocomplete"),
    path("solicitante-autocomplete/", SolicitanteAutocomplete.as_view(), name="solicitante-autocomplete"),
    path("funcao-autocomplete/", FuncaoAutocomplete.as_view(), name="funcao-autocomplete"),
    path("colaborador-autocomplete/", ColaboradorAutocomplete.as_view(), name="colaborador-autocomplete"),

    # APIs JSON para combobox inline (Tom Select)
    path("api/lojas/", views.api_lojas, name="api_lojas"),
    path("api/lojas/<int:loja_id>/quadro/", views.api_loja_quadro, name="api_loja_quadro"),
    path("api/colaboradores/", views.api_colaboradores, name="api_colaboradores"),
    path("api/solicitantes/", views.api_solicitantes, name="api_solicitantes"),
    path("api/funcoes/", views.api_funcoes, name="api_funcoes"),

    # drawer detalhe
    path("teste/<int:pk>/detalhe/", views.teste_detalhe, name="detalhe"),
    
    path("import/gestao-pessoas/", views.import_gestao_pessoas, name="import_gestao_pessoas"),
    path("import/gestao-pessoas/confirmar/", views.import_gestao_pessoas_confirm, name="import_gestao_pessoas_confirm"),
    
    path("exportar/", views.teste_exportar, name="teste_exportar"),
]


