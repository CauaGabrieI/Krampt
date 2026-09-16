from django.contrib import admin

from .models import DenunciaPost


@admin.register(DenunciaPost)
class DenunciaPostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "denunciante",
        "motivo",
        "status",
        "criado_em",
    )
    list_filter = ("status", "motivo", "criado_em")
    search_fields = (
        "post__conteudo",
        "post__autor__username",
        "denunciante__username",
        "denunciante__email",
        "detalhes",
    )
    list_editable = ("status",)
    raw_id_fields = ("post", "denunciante")
    readonly_fields = ("criado_em",)
    ordering = ("-criado_em",)
