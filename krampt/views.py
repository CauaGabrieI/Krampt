from django.shortcuts import render, redirect
from django.http import HttpResponse 
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.views.decorators.http import require_GET, require_POST
from posts.models import Post
from posts.http import obter_chave_idempotencia
from posts.services import filtrar_posts_visiveis, posts_para_exibir
from posts.forms import CriarPostForm
from profile.services import seguindo_ids
from .container import servico_comandos_post
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
            servico_comandos_post.criar_post(
                autor=request.user,
                conteudo=dados["conteudo"] or "",
                imagens=dados["imagem"],
                audio=dados.get("audio"),
                chave_idempotencia=obter_chave_idempotencia(request),
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
    
