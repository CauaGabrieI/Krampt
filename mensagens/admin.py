from django.contrib import admin

from .models import Conversa, Mensagem


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    readonly_fields = ("criada_em",)


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = ("pk", "criada_em")
    filter_horizontal = ("participantes",)
    inlines = [MensagemInline]


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ("pk", "conversa", "autor", "criada_em", "lida")
    list_filter = ("lida", "criada_em")
    search_fields = ("conteudo", "autor__username")
