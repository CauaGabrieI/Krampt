from django.contrib import admin
from django.urls import path, include
from . import views

app_name = "login"

urlpatterns = [

    path('', views.login_view, name='login'),
    path('senha/recuperar/', views.RedefinirSenhaView.as_view(), name='password_reset'),
    path(
        'senha/recuperar/enviado/',
        views.RedefinirSenhaDoneView.as_view(), name='password_reset_done',
    ),
    path(
        'senha/recuperar/confirmar/<uidb64>/<token>/',
        views.RedefinirSenhaConfirmView.as_view(), name='password_reset_confirm',
    ),
    path(
        'senha/recuperar/confirmar/<uidb64>/set-password/',
        views.RedefinirSenhaConfirmView.as_view(), name='password_reset_confirm_set',
    ),
    path(
        'senha/recuperar/concluido/',
        views.RedefinirSenhaCompleteView.as_view(), name='password_reset_complete',
    ),

]
