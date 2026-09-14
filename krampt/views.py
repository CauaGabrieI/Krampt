from django.shortcuts import render, redirect
from django.http import HttpResponse 
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.views.decorators.http import require_GET, require_POST
from posts.models import Post, ImagemPost
from django.db import transaction
from posts.services import comprimir_imagem_lossless, posts_para_exibir
from posts.forms import CriarPostForm
from profile.services import seguindo_ids

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
            with transaction.atomic():
                post = Post.objects.create(
                    autor=request.user,
                    conteudo=(dados["conteudo"] or "").strip(),
                    imagem=comprimir_imagem_lossless(imagens[0]) if imagens else "",
                    audio=dados.get("audio") or "",
                )
                for imagem in imagens[1:]:
                    ImagemPost.objects.create(post=post, imagem=comprimir_imagem_lossless(imagem))
            return redirect("home")

    if request.GET.get("filtro") == "seguindo":
        post_base = Post.objects.filter(autor_id__in=seguindo_ids(request.user))
        contexto = {"posts": posts_para_exibir(post_base, request.user), "filtro": "seguindo"}
    else:
        contexto = {"posts": posts_para_exibir(Post.objects.all(), request.user)}

    if request.method == "POST":
        contexto["formulario"] = formulario
    return render(request, "home.html", contexto)


@login_required
@require_GET
def buscar_view(request):
    termo = (request.GET.get("q") or "").strip()
    pessoas, posts = [], []
    if termo:
        pessoas = (
            User.objects.filter(Q(first_name__icontains=termo) | Q(username__icontains=termo))
            .exclude(pk=request.user.pk)
            .select_related("perfil")
            .order_by("username")[:20]
        )
        ids = list(
            Post.objects.filter(conteudo__icontains=termo).values_list("pk", flat=True)[:30]
        )
        posts = posts_para_exibir(Post.objects.filter(pk__in=ids), request.user) if ids else []
    return render(request, "buscar.html", {"termo": termo, "pessoas": pessoas, "posts": posts})
    
