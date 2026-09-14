"""
URL configuration for Krampt project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views

app_name = "posts"

urlpatterns = [
    path('', views.post_view, name='posts'),
    path("hashtag/<slug:slug>/", views.hashtag_view, name="hashtag"),
    path("<int:post_id>/editar/", views.editar_post, name="editar"),
    path("<int:post_id>/", views.detalhe_post, name="detalhe"),
    path("<int:post_id>/excluir/", views.excluir_post, name="excluir"),
    path("<int:post_id>/curtir/", views.curtir_post, name="curtir"),
    path("<int:post_id>/salvar/", views.salvar_post, name="salvar"),
    path("<int:post_id>/republicar/", views.republicar_post, name="republicar"),
    path("<int:post_id>/comentar/", views.comentar_post, name="comentar"),
    path("comentario/<int:comentario_id>/curtir/", views.curtir_comentario, name="curtir_comentario"),
    path("comentario/<int:comentario_id>/excluir/", views.excluir_comentario, name="excluir_comentario"),
    path("comentario/<int:comentario_id>/responder/", views.responder_comentario, name="responder_comentario"),

]
