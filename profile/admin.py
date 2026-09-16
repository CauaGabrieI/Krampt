from django.contrib import admin

from .models import DenunciaUsuario


@admin.register(DenunciaUsuario)
class DenunciaUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "alvo",
        "denunciante",
        "motivo",
        "status",
        "criado_em",
    )
    list_filter = ("status", "motivo", "criado_em")
    search_fields = (
        "alvo__username",
        "alvo__email",
        "denunciante__username",
        "denunciante__email",
        "detalhes",
    )
    list_editable = ("status",)
    raw_id_fields = ("alvo", "denunciante")
    readonly_fields = ("criado_em",)
    ordering = ("-criado_em",)
