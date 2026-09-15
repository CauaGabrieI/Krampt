from django.urls import path

from . import views

app_name = "notificacoes"

urlpatterns = [
    path("", views.notificacoes_view, name="lista"),
    path("marcar-todas-como-lidas/", views.marcar_todas_como_lidas, name="marcar_todas_como_lidas"),
    path("limpar/", views.limpar_notificacoes, name="limpar"),
    path("<int:notificacao_id>/excluir/", views.excluir_notificacao, name="excluir"),
]
