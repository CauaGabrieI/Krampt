from django.contrib import admin

from .models import PreferenciasUsuario


@admin.register(PreferenciasUsuario)
class PreferenciasUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tema", "mensagens_de", "notificacoes_site")
    list_select_related = ("usuario",)
    search_fields = ("usuario__username", "usuario__email")
