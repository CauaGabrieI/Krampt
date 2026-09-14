from django.urls import path

from . import views

app_name = "mensagens"

urlpatterns = [
    path("", views.lista_de_conversas, name="lista"),
    path("nova/", views.nova_conversa, name="nova"),
    path("criar/", views.criar_conversa, name="criar"),
    path("<int:conversa_id>/", views.conversa_view, name="detalhe"),
]
