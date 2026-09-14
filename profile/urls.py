from django.contrib import admin
from django.urls import path, include
from . import views

app_name = "profile"

urlpatterns = [
    path('', views.perfil_view, name='perfil'),
    path('editar/', views.editar_perfil_view, name='editar'),
    path('seguir/<int:usuario_id>/', views.seguir_usuario, name='seguir'),
    path('<str:username>/', views.perfil_publico_view, name='perfil_publico'),
]
