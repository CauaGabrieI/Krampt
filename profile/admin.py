from django.contrib import admin

from .models import DenunciaUsuario, Perfil


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "username",
        "verificado",
        "membro_da_equipe",
    )
    list_editable = ("verificado",)
    list_filter = ("verificado", "usuario__is_staff")
    list_select_related = ("usuario",)
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__email",
    )
    fields = ("usuario", "verificado")
    readonly_fields = ("usuario",)
    ordering = ("usuario__username",)

    @admin.display(description="Username", ordering="usuario__username")
    def username(self, obj):
        return f"@{obj.usuario.username}"

    @admin.display(boolean=True, description="Staff", ordering="usuario__is_staff")
    def membro_da_equipe(self, obj):
        return obj.usuario.is_staff

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
