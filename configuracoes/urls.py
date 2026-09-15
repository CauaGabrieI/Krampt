from django.urls import path

from . import views

app_name = "configuracoes"

urlpatterns = [
    path("", views.configuracoes_view, name="inicio"),
    path("dados/exportar/", views.exportar_dados, name="exportar_dados"),
    path("<slug:secao>/", views.configuracoes_view, name="secao"),
]
