from django.contrib import admin

from .models import EventoOutbox


@admin.register(EventoOutbox)
class EventoOutboxAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tipo",
        "tentativas",
        "criado_em",
        "disponivel_em",
        "processado_em",
        "descartado_em",
    )
    list_filter = (
        "tipo",
        "processado_em",
        "descartado_em",
    )
    search_fields = ("chave", "ultimo_erro")
    readonly_fields = (
        "tipo",
        "payload",
        "chave",
        "criado_em",
        "disponivel_em",
        "bloqueado_em",
        "processado_em",
        "descartado_em",
        "tentativas",
        "ultimo_erro",
    )
