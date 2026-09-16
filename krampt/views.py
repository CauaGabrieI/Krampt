from django.contrib.auth import logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
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


ADSENSE_ADS_TXT = "google.com, pub-9158694826036840, DIRECT, f08c47fec0942fa0"


@login_not_required
@require_GET
def ads_txt_view(request):
    return HttpResponse(
        ADSENSE_ADS_TXT + "\n",
        content_type="text/plain; charset=utf-8",
    )



@login_not_required
@require_GET
def sobre_view(request):
    return render(request, "public/sobre.html")


@login_not_required
@require_GET
def privacidade_view(request):
    return render(request, "public/privacidade.html")


@login_not_required
@require_GET
def termos_view(request):
    return render(request, "public/termos.html")


@login_not_required
@require_GET
def diretrizes_view(request):
    return render(request, "public/diretrizes.html")


@login_not_required
@require_GET
def robots_txt_view(request):
    linhas = [
        "User-agent: Mediapartners-Google",
        "Allow: /",
        "",
        "User-agent: Google-Display-Ads-Bot",
        "Allow: /",
        "",
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /configuracoes/",
        "Disallow: /mensagens/",
        "Disallow: /notificacoes/",
        "Disallow: /perfil/",
        "Disallow: /post/",
        "",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap_xml'))}",
        "",
    ]
    return HttpResponse(
        "\n".join(linhas),
        content_type="text/plain; charset=utf-8",
    )


@login_not_required
@require_GET
def sitemap_xml_view(request):
    nomes = (
        "home",
        "sobre",
        "diretrizes",
        "privacidade",
        "termos",
        "login:login",
        "cadastro",
    )
    urls = [
        request.build_absolute_uri(reverse(nome))
        for nome in nomes
    ]
    corpo = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    corpo.extend(f"  <url><loc>{url}</loc></url>" for url in urls)
    corpo.append("</urlset>")
    corpo.append("")
    return HttpResponse(
        "\n".join(corpo),
        content_type="application/xml; charset=utf-8",
    )


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("login:login")


@login_not_required
def Index_view(request):
    if not request.user.is_authenticated:
        if request.method != "GET":
            return redirect("login:login")
        return render(request, "public/home.html")

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
