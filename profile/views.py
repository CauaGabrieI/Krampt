from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from krampt.container import servico_relacionamentos
from krampt.paginacao import parametros_sem_pagina, paginar
from posts.http import obter_estado_desejado
from posts.services import usuario_bloqueado_entre

from .forms import DenunciaUsuarioForm, EditarPerfilForm
from .models import DenunciaUsuario, Perfil
from .selectors import conteudo_do_perfil, queryset_relacoes
from .services import perfil_do, salvar_edicao_perfil


User = get_user_model()


@login_required
@require_GET
def perfil_view(request):
    perfil = perfil_do(request.user)
    contexto = {
        **conteudo_do_perfil(
            request.user,
            request.user,
            request.GET.get("aba"),
            request.GET.get("page"),
        ),
        "perfil": perfil,
        "seguindo": perfil.seguindo.count() if perfil else 0,
        "seguidores": request.user.seguidores.count(),
        "parametros_url": parametros_sem_pagina(request),
    }
    return render(request, "perfil.html", contexto)


@login_required
@require_GET
def perfil_publico_view(request, username):
    usuario = get_object_or_404(User, username=username)
    if usuario.pk == request.user.pk:
        return redirect("profile:perfil")

    perfil = perfil_do(usuario)
    bloqueado = usuario_bloqueado_entre(request.user, usuario)
    contexto = {
        "perfil_usuario": usuario,
        "perfil": perfil,
        "bloqueado": bloqueado,
        "seguindo": perfil.seguindo.count() if perfil else 0,
        "seguidores": usuario.seguidores.count(),
        "parametros_url": parametros_sem_pagina(request),
    }

    if bloqueado:
        contexto.update(
            {
                "aba": "publicacoes",
                "posts": [],
                "post_fixado": None,
                "pagina_objeto": None,
                "total_posts": 0,
                "total_publicacoes": 0,
                "total_repostados": 0,
                "total_midia": 0,
                "total_salvos": 0,
                "pode_ver_salvos": False,
            }
        )
    else:
        contexto.update(
            conteudo_do_perfil(
                usuario,
                request.user,
                request.GET.get("aba"),
                request.GET.get("page"),
            )
        )

    return render(request, "perfil_publico.html", contexto)


@login_required
@require_GET
def relacoes_perfil_view(request, username, tipo):
    usuario = get_object_or_404(User, username=username)
    bloqueado = (
        usuario.pk != request.user.pk
        and usuario_bloqueado_entre(request.user, usuario)
    )

    pagina_objeto = None
    if not bloqueado:
        pagina_objeto = paginar(
            queryset_relacoes(usuario, tipo, request.user),
            request.GET.get("page"),
            por_pagina=30,
        )

    return render(
        request,
        "perfil_relacoes.html",
        {
            "dono_do_perfil": usuario,
            "tipo": tipo,
            "titulo": "Seguindo" if tipo == "seguindo" else "Seguidores",
            "bloqueado": bloqueado,
            "pagina_objeto": pagina_objeto,
            "parametros_url": parametros_sem_pagina(request),
        },
    )


@login_required
@require_POST
def seguir_usuario(request, usuario_id):
    alvo = get_object_or_404(User, pk=usuario_id)
    destino = request.POST.get("next") or request.META.get(
        "HTTP_REFERER",
        "",
    )
    if not url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destino = reverse("home")

    servico_relacionamentos.definir_seguindo(
        request.user,
        alvo,
        obter_estado_desejado(request),
    )
    return redirect(destino)


@login_required
@require_POST
def denunciar_usuario(request, username):
    alvo = get_object_or_404(User, username=username)
    if alvo.pk == request.user.pk:
        return HttpResponseForbidden("Você não pode denunciar o próprio perfil.")

    destino = request.POST.get("return_path") or reverse(
        "profile:perfil_publico",
        args=[alvo.username],
    )
    if not url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destino = reverse("profile:perfil_publico", args=[alvo.username])

    formulario = DenunciaUsuarioForm(request.POST)
    if not formulario.is_valid():
        messages.error(request, "Escolha um motivo válido para a denúncia.")
        return redirect(destino)

    _, criada = DenunciaUsuario.objects.get_or_create(
        denunciante=request.user,
        alvo=alvo,
        defaults={
            "motivo": formulario.cleaned_data["motivo"],
            "detalhes": formulario.cleaned_data["detalhes"].strip(),
        },
    )

    if criada:
        messages.success(request, f"Denúncia contra @{alvo.username} enviada.")
    else:
        messages.info(request, f"Você já denunciou @{alvo.username}.")

    return redirect(destino)


@login_required
@require_http_methods(["GET", "POST"])
def editar_perfil_view(request):
    perfil = Perfil.objects.filter(usuario=request.user).first()

    if request.method == "POST":
        formulario = EditarPerfilForm(request.POST, request.FILES)
        if formulario.is_valid():
            salvar_edicao_perfil(
                request.user,
                perfil,
                formulario.cleaned_data,
            )
            return redirect("profile:perfil")
    else:
        formulario = EditarPerfilForm(
            initial={
                "nome": request.user.first_name or request.user.username,
                "biografia": perfil.biografia if perfil else "",
            }
        )

    return render(
        request,
        "editar_perfil.html",
        {
            "formulario": formulario,
            "perfil": perfil,
        },
    )
