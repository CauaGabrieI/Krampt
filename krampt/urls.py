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
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from login.views import (
    cadastro_view,
    reativar_conta_token_view,
    reativar_conta_view,
    verificar_email_view,
)
from login.admin_views import (
    apagar_usuarios_view,
    testar_email_view,
    verificar_usuarios_view,
)
from . import views



urlpatterns = [ 
    path('ads.txt', views.ads_txt_view, name='ads_txt'),
    path('', views.Index_view, name='home'),
    path('buscar/', views.buscar_view, name='buscar'),
    path('mensagens/', include("mensagens.urls")),
    path('cadastro/', cadastro_view, name='cadastro'),
    path('verificar-email/', verificar_email_view, name='verificar_email'),
    path('conta/reativar/', reativar_conta_view, name='reativar_conta'),
    path('conta/reativar/<str:token>/', reativar_conta_token_view, name='reativar_conta_token'),
    path('admin/testar-email/', testar_email_view, name='testar_email'),
    path('admin/apagar-usuarios/', apagar_usuarios_view, name='admin_apagar_usuarios'),
    path('admin/verificar-usuarios/', verificar_usuarios_view, name='admin_verificar_usuarios'),
    path('admin/', admin.site.urls),
    path('perfil/', include("profile.urls")),
    path('login/', include("login.urls")),
    path('post/', include("posts.urls")),
    path('notificacoes/', include("notificacoes.urls")),
    path('configuracoes/', include("configuracoes.urls")),
    path("logout/", views.logout_view, name="logout"),

]

if settings.DEBUG and not settings.R2_ENABLED:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
