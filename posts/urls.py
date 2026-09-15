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
from django.urls import path
from . import views

app_name = "posts"

urlpatterns = [
    path("hashtag/<slug:slug>/", views.hashtag_view, name="hashtag"),
    path("<int:post_id>/editar/", views.editar_post, name="editar"),
    path("<int:post_id>/", views.detalhe_post, name="detalhe"),
    path("<int:post_id>/excluir/", views.excluir_post, name="excluir"),
    path("<int:post_id>/curtir/", views.curtir_post, name="curtir"),
    path("<int:post_id>/salvar/", views.salvar_post, name="salvar"),
    path("<int:post_id>/republicar/", views.republicar_post, name="republicar"),
    path("<int:post_id>/ignorar/", views.ignorar_post, name="ignorar"),
    path("<int:post_id>/desocultar/", views.desocultar_post_view, name="desocultar"),
    path("<int:post_id>/fixar/", views.fixar_post, name="fixar"),
    path("<int:post_id>/atividade/", views.atividade_post, name="atividade"),
    path("<int:post_id>/denunciar/", views.denunciar_post, name="denunciar"),
    path("<int:post_id>/comentar/", views.comentar_post, name="comentar"),
    path("usuario/<int:usuario_id>/silenciar/", views.silenciar_usuario, name="silenciar_usuario"),
    path("usuario/<int:usuario_id>/dessilenciar/", views.dessilenciar_usuario_view, name="dessilenciar_usuario"),
    path("usuario/<int:usuario_id>/bloquear/", views.bloquear_usuario_view, name="bloquear_usuario"),
    path("usuario/<int:usuario_id>/desbloquear/", views.desbloquear_usuario_view, name="desbloquear_usuario"),
    path("comentario/<int:comentario_id>/curtir/", views.curtir_comentario, name="curtir_comentario"),
    path("comentario/<int:comentario_id>/excluir/", views.excluir_comentario, name="excluir_comentario"),
    path("comentario/<int:comentario_id>/responder/", views.responder_comentario, name="responder_comentario"),

]
