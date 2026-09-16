from django.shortcuts import render, redirect
from django.http import HttpResponse 
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.views.decorators.http import require_GET, require_POST
from posts.models import Post, ImagemPost
from django.db import transaction
from posts.services import (
    bloquear_usuarios_para_mutacao,
    comprimir_imagem_lossless,
    filtrar_posts_visiveis,
    obter_chave_idempotencia,
    posts_para_exibir,
)
from posts.forms import CriarPostForm
from profile.services import seguindo_ids
from .paginacao import parametros_sem_pagina, paginar

User = get_user_model()


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("login:login")

@login_required
def Index_view(request):
    if request.method == "POST":
        formulario = CriarPostForm(request.POST, request.FILES)
        if formulario.is_valid():
            dados = formulario.cleaned_data
            imagens = dados["imagem"]
            chave = obter_chave_idempotencia(request)
            with transaction.atomic():
                if chave:
                    bloquear_usuarios_para_mutacao(request.user)
                    existente = Post.objects.filter(
                        autor=request.user,
                        original__isnull=True,
                        chave_idempotencia=chave,
                    ).first()
                    if existente is not None:
                        return redirect("home")

                post = Post.objects.create(
                    autor=request.user,
                    conteudo=(dados["conteudo"] or "").strip(),
                    imagem=comprimir_imagem_lossless(imagens[0]) if imagens else "",
                    audio=dados.get("audio") or "",
                    chave_idempotencia=chave,
                )
                for imagem in imagens[1:]:
                    ImagemPost.objects.create(
                        post=post,
                        imagem=comprimir_imagem_lossless(imagem),
                    )
            return redirect("home")

    if request.GET.get("filtro") == "seguindo":
        post_base = Post.objects.filter(autor_id__in=seguindo_ids(request.user))
        filtro = "seguindo"
    else:
        post_base = Post.objects.all()
        filtro = ""
    post_base = filtrar_posts_visiveis(post_base, request.user).order_by("-criado_em", "-pk")
    pagina = paginar(post_base, request.GET.get("page"))
    contexto = {
        "posts": posts_para_exibir(pagina.object_list, request.user, incluir_comentarios=False),
        "pagina_objeto": pagina,
        "parametros_url": parametros_sem_pagina(request),
        "filtro": filtro,
    }

    if request.method == "POST":
        contexto["formulario"] = formulario
    return render(request, "home.html", contexto)

@login_required
@require_GET
def buscar_view(request):
    termo = (request.GET.get("q") or "").strip()
    pessoas, posts, pagina_final = [], [], None
    if termo:
        pessoas = (
            User.objects.filter(Q(first_name__icontains=termo) | Q(username__icontains=termo))
            .exclude(pk=request.user.pk)
            .select_related("perfil")
            .order_by("username")[:20]
        )
        pagina_final = paginar(
            filtrar_posts_visiveis(
                Post.objects.filter(conteudo__icontains=termo),
                request.user,
            ).order_by("-criado_em", "-pk"),
            request.GET.get("page"),
        )
        posts = posts_para_exibir(
            pagina_final.object_list, request.user, incluir_comentarios=False
        )
    return render(
        request,
        "buscar.html",
        {
            "termo": termo,
            "pessoas": pessoas,
            "posts": posts,
            "pagina_objeto": pagina_final,
            "parametros_url": parametros_sem_pagina(request),
        },
    )
    
