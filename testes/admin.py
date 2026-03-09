from django.contrib import admin
from .models import Regiao, Loja, Solicitante, TestePromocao, PremioPago, Funcao, AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "teste", "user", "ip")
    list_filter = ("action", "created_at")
    search_fields = ("teste__colaborador_nome", "teste__colaborador_re", "user__username", "note", "ip")
    readonly_fields = ("created_at",)


class AuditLogInline(admin.TabularInline):
    model = AuditLog
    extra = 0
    can_delete = False
    readonly_fields = ("created_at", "user", "action", "ip", "user_agent", "note")
    fields = ("created_at", "user", "action", "note", "ip")
    ordering = ("-created_at",)


@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    search_fields = ("nome",)
    list_display = ("nome", "regiao")
    list_filter = ("regiao",)


@admin.register(Regiao)
class RegiaoAdmin(admin.ModelAdmin):
    search_fields = ("nome",)


@admin.register(Solicitante)
class SolicitanteAdmin(admin.ModelAdmin):
    search_fields = ("nome",)


@admin.register(Funcao)
class FuncaoAdmin(admin.ModelAdmin):
    search_fields = ("nome",)
    ordering = ("nome",)


class PremioInline(admin.TabularInline):
    model = PremioPago
    extra = 0


@admin.register(TestePromocao)
class TestePromocaoAdmin(admin.ModelAdmin):
    autocomplete_fields = ("loja", "solicitante")
    search_fields = ("colaborador_nome", "colaborador_re", "funcao__nome", "loja__nome")
    list_filter = ("status", "loja__regiao", "loja", "solicitante")
    inlines = [PremioInline, AuditLogInline]  # <-- opcional: ver logs dentro do teste


@admin.register(PremioPago)
class PremioPagoAdmin(admin.ModelAdmin):
    list_display = ("teste", "numero_premio", "data_pagamento")
    search_fields = ("teste__colaborador_nome", "teste__colaborador_re")
    list_filter = ("data_pagamento",)
