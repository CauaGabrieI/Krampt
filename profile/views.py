from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from django.db.models import Count, Q
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from posts.models import Post, ImagemPost
from posts.services import posts_para_exibir
from notificacoes.services import notificar, remover_notificacao
from .forms import EditarPerfilForm
from .models import Perfil
from .services import perfil_do, redimensionar_banner

User = get_user_model()


def _conteudo_do_perfil(usuario, visitante, aba):
    pode_ver_salvos = usuario.pk == visitante.pk
    abas_validas = {"publicacoes", "repostados", "midia"}
    if pode_ver_salvos:
        abas_validas.add("salvos")
    if aba not in abas_validas:
        aba = "publicacoes"
    todos = Post.objects.filter(autor=usuario)
    totais = todos.aggregate(
        publicacoes=Count("pk", filter=Q(original__isnull=True)),
        repostados=Count("pk", filter=Q(original__isnull=False)),
        midia=Count("pk", filter=Q(original__isnull=True) & ~Q(imagem="")),
    )
    total_salvos = Post.objects.filter(
        salvos_por=visitante, original__isnull=True
    ).count() if pode_ver_salvos else 0
    if aba == "salvos":
        exibidos = Post.objects.filter(salvos_por=visitante, original__isnull=True)
    elif aba == "repostados":
        exibidos = todos.filter(original__isnull=False)
    elif aba == "midia":
        exibidos = todos.filter(original__isnull=True).exclude(imagem="")
    else:
        exibidos = todos.filter(original__isnull=True)
    return {
        "aba": aba,
        "posts": posts_para_exibir(exibidos, visitante),
        "total_posts": totais["publicacoes"] + totais["repostados"],
        "total_publicacoes": totais["publicacoes"],
        "total_repostados": totais["repostados"],
        "total_midia": totais["midia"] + ImagemPost.objects.filter(
            post__autor=usuario, post__original__isnull=True
        ).count(),
        "total_salvos": total_salvos,
        "pode_ver_salvos": pode_ver_salvos,
    }


@login_required
@require_GET
def perfil_view(request):
    perfil = perfil_do(request.user)
    contexto = {
        **_conteudo_do_perfil(request.user, request.user, request.GET.get("aba")),
        "perfil": perfil,
        "seguindo": perfil.seguindo.count() if perfil else 0,
        "seguidores": request.user.seguidores.count(),
    }
    return render(request, "perfil.html", contexto)


@login_required
@require_GET
def perfil_publico_view(request, username):
    usuario = get_object_or_404(User, username=username)
    if usuario.pk == request.user.pk:
        return redirect("profile:perfil")
    perfil = perfil_do(usuario)
    contexto = {
        "perfil_usuario": usuario,
        "perfil": perfil,
        **_conteudo_do_perfil(usuario, request.user, request.GET.get("aba")),
        "seguindo": perfil.seguindo.count() if perfil else 0,
        "seguidores": usuario.seguidores.count(),
    }
    return render(request, "perfil_publico.html", contexto)


@login_required
@require_POST
def seguir_usuario(request, usuario_id):
    alvo = get_object_or_404(User, pk=usuario_id)
    if alvo != request.user:
        perfil, _ = Perfil.objects.get_or_create(usuario=request.user)
        if perfil.seguindo.filter(pk=alvo.pk).exists():
            perfil.seguindo.remove(alvo)
            remover_notificacao(alvo, "seguidor", request.user)
        else:
            perfil.seguindo.add(alvo)
            notificar(alvo, "seguidor", request.user)
    destino = request.POST.get("next") or request.META.get("HTTP_REFERER", "")
    if not url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        destino = reverse("home")
    return redirect(destino)


@login_required
@require_http_methods(["GET", "POST"])
def editar_perfil_view(request):
    perfil = Perfil.objects.filter(usuario=request.user).first()
    if request.method == "POST":
        formulario = EditarPerfilForm(request.POST, request.FILES)
        if formulario.is_valid():
            foto_anterior = perfil.foto.name if perfil and perfil.foto else None
            banner_anterior = perfil.banner.name if perfil and perfil.banner else None
            dados = formulario.cleaned_data
            with transaction.atomic():
                request.user.first_name = dados["nome"]
                request.user.save(update_fields=["first_name"])
                if perfil is None:
                    perfil = Perfil(usuario=request.user)
                perfil.biografia = dados["biografia"]
                if dados["foto"]:
                    perfil.foto = dados["foto"]
                elif dados["remover_foto"]:
                    perfil.foto = ""
                if dados["banner"]:
                    perfil.banner = redimensionar_banner(dados["banner"])
                elif dados["remover_banner"]:
                    perfil.banner = ""
                perfil.save()
            if foto_anterior and foto_anterior != perfil.foto.name:
                perfil.foto.storage.delete(foto_anterior)
            if banner_anterior and banner_anterior != perfil.banner.name:
                perfil.banner.storage.delete(banner_anterior)
            return redirect("profile:perfil")
    else:
        formulario = EditarPerfilForm(initial={
            "nome": request.user.first_name or request.user.username,
            "biografia": perfil.biografia if perfil else "",
        })
    return render(request, "editar_perfil.html", {"formulario": formulario, "perfil": perfil})
