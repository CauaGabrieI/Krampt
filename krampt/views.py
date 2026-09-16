from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from posts.forms import CriarPostForm
from posts.http import obter_chave_idempotencia
from posts.selectors import (
    buscar_pessoas,
    preparar_posts,
    queryset_busca_posts,
    queryset_feed,
)

from .container import servico_comandos_post
from .paginacao import parametros_sem_pagina, paginar


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
            servico_comandos_post.criar_post(
                autor=request.user,
                conteudo=dados["conteudo"] or "",
                imagens=dados["imagem"],
                audio=dados.get("audio"),
                chave_idempotencia=obter_chave_idempotencia(request),
            )
            return redirect("home")

    post_base, filtro = queryset_feed(
        request.user,
        request.GET.get("filtro"),
    )
    pagina = paginar(post_base, request.GET.get("page"))
    contexto = {
        "posts": preparar_posts(
            pagina.object_list,
            request.user,
            incluir_comentarios=False,
        ),
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
        pessoas = buscar_pessoas(termo, request.user)
        pagina_final = paginar(
            queryset_busca_posts(termo, request.user),
            request.GET.get("page"),
        )
        posts = preparar_posts(
            pagina_final.object_list,
            request.user,
            incluir_comentarios=False,
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
