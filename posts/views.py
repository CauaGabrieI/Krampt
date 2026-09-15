from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from notificacoes.services import notificar, remover_notificacao
from krampt.paginacao import parametros_sem_pagina, paginar
from profile.models import Perfil
from .models import (
    Comentario,
    DenunciaPost,
    Hashtag,
    Post,
    PostSemInteresse,
    UsuarioSilenciado,
)
from .forms import ComentarioForm, DenunciaPostForm, EditarPostForm
from .services import (
    bloquear_usuario,
    comprimir_imagem_lossless,
    conteudo_com_hashtags,
    filtrar_posts_visiveis,
    posts_para_exibir,
)

User = get_user_model()


def _pagina_de_retorno(request):
    caminho = request.POST.get("return_path", "")
    if url_has_allowed_host_and_scheme(
        caminho, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return caminho
    return None


def _resposta_ajax(request, **dados):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(dados)
    return None


def _erro_comentario(request, formulario, post_id):
    erro = next(iter(formulario.errors.values()))[0]
    resposta = _resposta_ajax(request, created=False, error=str(erro))
    if resposta is not None:
        resposta.status_code = 400
        return resposta
    messages.error(request, erro)
    return redirect("posts:detalhe", post_id=post_id)


@login_required
def detalhe_post(request, post_id):
    post = get_object_or_404(
        filtrar_posts_visiveis(Post.objects.filter(original__isnull=True), request.user),
        pk=post_id,
    )
    entrada = posts_para_exibir(Post.objects.filter(pk=post.pk), request.user)[0]
    return render(request, "post_detalhe.html", {"post": entrada})


@login_required
def hashtag_view(request, slug):
    hashtag = get_object_or_404(Hashtag, slug=slug)
    base = (
        filtrar_posts_visiveis(
            Post.objects.filter(Q(hashtags=hashtag) | Q(comentarios__hashtags=hashtag)),
            request.user,
        )
        .distinct()
        .order_by("-criado_em", "-pk")
    )
    pagina = paginar(base, request.GET.get("page"))
    posts = posts_para_exibir(
        pagina.object_list, request.user, incluir_comentarios=False
    )
    return render(
        request,
        "hashtag.html",
        {
            "hashtag": hashtag,
            "posts": posts,
            "pagina_objeto": pagina,
            "parametros_url": parametros_sem_pagina(request),
        },
    )


@login_required
def editar_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id, autor=request.user, original__isnull=True)
    if request.method == "POST":
        formulario = EditarPostForm(request.POST)
        if formulario.is_valid():
            post.conteudo = formulario.cleaned_data["conteudo"].strip()
            post.editado_em = timezone.now()
            post.save(update_fields=["conteudo", "editado_em"])
            return redirect(_pagina_de_retorno(request) or "home")
    else:
        formulario = EditarPostForm(initial={"conteudo": post.conteudo})
    return render(request, "editar_post.html", {"post": post, "formulario": formulario})

@login_required
@require_POST
def excluir_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, autor=request.user)
    post.delete()
    resposta = _resposta_ajax(request, deleted=True)
    if resposta:
        return resposta
    return redirect(_pagina_de_retorno(request) or "home")


def _voltar_para_posts(request, post_id=None):
    pagina_de_retorno = _pagina_de_retorno(request)
    if pagina_de_retorno:
        entrada_id = request.POST.get("entry_id", "")
        if entrada_id.isascii() and entrada_id.isdigit():
            pagina_de_retorno += f"#post-{entrada_id}"
        return redirect(pagina_de_retorno)
    if request.POST.get("return_to") == "post" and post_id:
        return redirect("posts:detalhe", post_id=post_id)

    destino = None
    if request.POST.get("return_to") == "perfil" and post_id:
        autor = Post.objects.get(pk=post_id).autor
        destino = reverse("profile:perfil_publico", args=[autor.username])
    else:
        pagina = "profile:perfil" if request.POST.get("return_to") == "profile" else "home"
        destino = reverse(pagina)
    entrada_id = request.POST.get("entry_id", "")
    if entrada_id.isascii() and entrada_id.isdigit():
        destino += f"#post-{entrada_id}"
    return redirect(destino)


@login_required
@require_POST
def curtir_post(request, post_id):
    post = get_object_or_404(
        filtrar_posts_visiveis(Post.objects.filter(original__isnull=True), request.user),
        pk=post_id,
    )
    curtida, criada = Post.curtidas.through.objects.get_or_create(
        post_id=post.pk, user_id=request.user.pk
    )
    if not criada:
        curtida.delete()
        remover_notificacao(post.autor, "curtida", request.user, post=post)
    else:
        notificar(post.autor, "curtida", request.user, post=post)
    resposta = _resposta_ajax(
        request,
        liked=criada,
        total=post.curtidas.count(),
    )
    if resposta:
        return resposta
    return _voltar_para_posts(request, post.pk)


@login_required
@require_POST
def salvar_post(request, post_id):
    post = get_object_or_404(
        filtrar_posts_visiveis(Post.objects.filter(original__isnull=True), request.user),
        pk=post_id,
    )
    salvo = post.salvos_por.filter(pk=request.user.pk).exists()
    if salvo:
        post.salvos_por.remove(request.user)
    else:
        post.salvos_por.add(request.user)
    resposta = _resposta_ajax(request, saved=not salvo)
    if resposta:
        return resposta
    return _voltar_para_posts(request, post.pk)


@login_required
@require_POST
def ignorar_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id, original__isnull=True)
    PostSemInteresse.objects.get_or_create(usuario=request.user, post=post)
    messages.success(request, "Post ocultado.")
    resposta = _resposta_ajax(request, hidden=True, message="Post ocultado.")
    if resposta:
        return resposta
    return redirect(_pagina_de_retorno(request) or "home")


@login_required
@require_POST
def silenciar_usuario(request, usuario_id):
    silenciado = get_object_or_404(User, pk=usuario_id)
    if silenciado.pk == request.user.pk:
        return HttpResponseForbidden("Você não pode silenciar a própria conta.")
    UsuarioSilenciado.objects.get_or_create(usuario=request.user, silenciado=silenciado)
    messages.success(request, f"@{silenciado.username} foi silenciado.")
    resposta = _resposta_ajax(request, muted=True, message=f"@{silenciado.username} foi silenciado.")
    if resposta:
        return resposta
    return redirect(_pagina_de_retorno(request) or "home")


@login_required
@require_POST
def bloquear_usuario_view(request, usuario_id):
    bloqueado = get_object_or_404(User, pk=usuario_id)
    if not bloquear_usuario(request.user, bloqueado):
        return HttpResponseForbidden("Você não pode bloquear a própria conta.")
    messages.success(request, f"@{bloqueado.username} foi bloqueado.")
    resposta = _resposta_ajax(request, blocked=True, message=f"@{bloqueado.username} foi bloqueado.")
    if resposta:
        return resposta
    return redirect(_pagina_de_retorno(request) or "home")


@login_required
@require_POST
def fixar_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id, autor=request.user, original__isnull=True)
    perfil, _ = Perfil.objects.get_or_create(usuario=request.user)
    if perfil.post_fixado_id == post.pk:
        perfil.post_fixado = None
        mensagem = "Post desafixado."
    else:
        perfil.post_fixado = post
        mensagem = "Post fixado no perfil."
    perfil.save(update_fields=["post_fixado"])
    messages.success(request, mensagem)
    resposta = _resposta_ajax(request, pinned=perfil.post_fixado_id == post.pk)
    if resposta:
        return resposta
    return _voltar_para_posts(request, post.pk)


@login_required
def atividade_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id, autor=request.user, original__isnull=True)
    post.conteudo_formatado = conteudo_com_hashtags(post.conteudo)
    return render(
        request,
        "atividade_post.html",
        {
            "post": post,
            "total_curtidas": post.curtidas.count(),
            "total_comentarios": post.comentarios.count(),
            "total_republicacoes": post.republicacoes.count(),
            "total_salvos": post.salvos_por.count(),
        },
    )


@login_required
@require_POST
def denunciar_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id, original__isnull=True)
    if post.autor_id == request.user.pk:
        return HttpResponseForbidden("Você não pode denunciar o próprio post.")
    formulario = DenunciaPostForm(request.POST)
    if not formulario.is_valid():
        messages.error(request, "Escolha um motivo válido para a denúncia.")
        return redirect(_pagina_de_retorno(request) or reverse("posts:detalhe", args=[post.pk]))
    denuncia, criada = DenunciaPost.objects.get_or_create(
        denunciante=request.user,
        post=post,
        defaults={
            "motivo": formulario.cleaned_data["motivo"],
            "detalhes": formulario.cleaned_data["detalhes"].strip(),
        },
    )
    if not criada:
        messages.warning(request, "Você já denunciou este post.")
    else:
        messages.success(request, "Denúncia enviada.")
    resposta = _resposta_ajax(request, reported=criada)
    if resposta:
        return resposta
    return redirect(_pagina_de_retorno(request) or reverse("posts:detalhe", args=[post.pk]))


@login_required
@require_POST
def republicar_post(request, post_id):
    post = get_object_or_404(
        filtrar_posts_visiveis(Post.objects.filter(original__isnull=True), request.user),
        pk=post_id,
    )
    republicacao, criada = Post.objects.get_or_create(
        autor=request.user, original=post, defaults={"conteudo": ""}
    )
    if not criada:
        republicacao.delete()
        remover_notificacao(post.autor, "repost", request.user, post=post)
    else:
        notificar(post.autor, "repost", request.user, post=post)
    resposta = _resposta_ajax(
        request,
        reposted=criada,
        total=post.republicacoes.count(),
    )
    if resposta:
        return resposta
    return _voltar_para_posts(request, post.pk)


@login_required
@require_POST
def comentar_post(request, post_id):
    post = get_object_or_404(
        filtrar_posts_visiveis(Post.objects.filter(original__isnull=True), request.user),
        pk=post_id,
    )
    formulario = ComentarioForm(request.POST, request.FILES)
    if not formulario.is_valid():
        return _erro_comentario(request, formulario, post.pk)
    dados = formulario.cleaned_data
    comentario = Comentario.objects.create(
        post=post,
        autor=request.user,
        conteudo=dados["conteudo"],
        imagem=comprimir_imagem_lossless(dados.get("imagem")) if dados.get("imagem") else "",
        audio=dados.get("audio") or "",
    )
    notificar(post.autor, "comentario", request.user, post=post, comentario=comentario)
    resposta = _resposta_ajax(request, created=True)
    if resposta:
        return resposta
    return _voltar_para_posts(request, post.pk)


@login_required
@require_POST
def curtir_comentario(request, comentario_id):
    comentario = get_object_or_404(
        Comentario.objects.filter(
            post__in=filtrar_posts_visiveis(Post.objects.filter(original__isnull=True), request.user)
        ),
        pk=comentario_id,
    )
    curtida, criada = Comentario.curtidas.through.objects.get_or_create(
        comentario_id=comentario.pk, user_id=request.user.pk
    )
    if not criada:
        curtida.delete()
        remover_notificacao(
            comentario.autor,
            "curtida_comentario",
            request.user,
            post=comentario.post,
            comentario=comentario,
        )
    else:
        notificar(
            comentario.autor,
            "curtida_comentario",
            request.user,
            post=comentario.post,
            comentario=comentario,
        )
    resposta = _resposta_ajax(
        request,
        liked=criada,
        total=comentario.curtidas.count(),
    )
    if resposta:
        return resposta
    return _voltar_para_posts(request, comentario.post_id)


@login_required
@require_POST
def excluir_comentario(request, comentario_id):
    comentario = get_object_or_404(Comentario, pk=comentario_id, autor=request.user)
    post_id = comentario.post_id
    comentario.delete()
    resposta = _resposta_ajax(request, deleted=True)
    if resposta:
        return resposta
    return _voltar_para_posts(request, post_id)


@login_required
@require_POST
def responder_comentario(request, comentario_id):
    comentario = get_object_or_404(
        Comentario.objects.filter(
            post__in=filtrar_posts_visiveis(Post.objects.filter(original__isnull=True), request.user)
        ),
        pk=comentario_id,
    )
    formulario = ComentarioForm(request.POST, request.FILES)
    if not formulario.is_valid():
        return _erro_comentario(request, formulario, comentario.post_id)
    dados = formulario.cleaned_data
    resposta = Comentario.objects.create(
        post=comentario.post,
        autor=request.user,
        resposta_para=comentario.resposta_para or comentario,
        conteudo=dados["conteudo"],
        imagem=comprimir_imagem_lossless(dados.get("imagem")) if dados.get("imagem") else "",
        audio=dados.get("audio") or "",
    )
    notificar(
        comentario.autor,
        "resposta",
        request.user,
        post=comentario.post,
        comentario=resposta,
    )
    resposta_ajax = _resposta_ajax(request, created=True)
    if resposta_ajax:
        return resposta_ajax
    return _voltar_para_posts(request, comentario.post_id)
