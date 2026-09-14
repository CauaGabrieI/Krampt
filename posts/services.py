import re
from io import BytesIO

from django.db.models import Count, Exists, OuterRef, Prefetch
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils.html import escape, urlize
from django.utils.text import slugify
from django.utils.safestring import mark_safe

from .models import Comentario, Post

LINK_OU_HASHTAG_RE = re.compile(
    r"https?://[^\s<>]+|www\.[^\s<>]+|(?<![\w#])#[\w]+",
    re.IGNORECASE | re.UNICODE,
)

MAX_LADO_IMAGEM = 8000
MAX_PIXELS_IMAGEM = 30_000_000
MAX_FRAMES_GIF = 150


def validar_limites_da_imagem(arquivo):
    """Valida dimensão, total de pixels e quadros de GIF.

    Retorna (ok, mensagem). Não desloca o cursor do arquivo.
    """
    from io import BytesIO

    from PIL import Image

    posicao = arquivo.tell()
    arquivo.seek(0)
    dados = arquivo.read()
    arquivo.seek(posicao)
    try:
        with Image.open(BytesIO(dados)) as imagem:
            try:
                largura, altura = imagem.size
            except (Image.DecompressionBombError, ValueError, OSError):
                return False, "Não foi possível ler as dimensões da imagem."
            if largura > MAX_LADO_IMAGEM or altura > MAX_LADO_IMAGEM:
                return False, f"A imagem deve ter no máximo {MAX_LADO_IMAGEM} pixels por lado."
            if largura * altura > MAX_PIXELS_IMAGEM:
                return False, "A imagem tem pixels demais para ser processada."
            if getattr(imagem, "n_frames", 1) > MAX_FRAMES_GIF:
                return False, f"GIFs animados devem ter no máximo {MAX_FRAMES_GIF} quadros."
            return True, ""
    except (Image.DecompressionBombError, ValueError, OSError):
        return False, "Não foi possível processar a imagem."


def comprimir_imagem_lossless(uploaded_file):
    if not uploaded_file or getattr(uploaded_file, "image", None) is None:
        return uploaded_file

    formato = uploaded_file.image.format
    if formato not in {"PNG", "GIF", "WEBP"}:
        return uploaded_file

    from PIL import Image

    uploaded_file.seek(0)
    imagem = Image.open(uploaded_file)
    saida = BytesIO()
    opcoes = {"format": formato, "optimize": True}
    if formato == "WEBP":
        opcoes["lossless"] = True
    if formato == "GIF" and getattr(imagem, "is_animated", False):
        frames = []
        duracoes = []
        for frame in range(imagem.n_frames):
            imagem.seek(frame)
            frames.append(imagem.convert("RGBA"))
            duracoes.append(imagem.info.get("duration", 0))
        frames[0].save(saida, save_all=True, append_images=frames[1:], duration=duracoes, loop=imagem.info.get("loop", 0), **opcoes)
    else:
        imagem.save(saida, **opcoes)
    if saida.tell() >= uploaded_file.size:
        uploaded_file.seek(0)
        return uploaded_file
    return ContentFile(saida.getvalue(), name=uploaded_file.name)


def hashtags_do_texto(texto):
    encontrados = {}
    for correspondencia in LINK_OU_HASHTAG_RE.finditer(texto or ""):
        if not correspondencia.group(0).startswith("#"):
            continue
        nome = correspondencia.group(0)[1:]
        slug = slugify(nome)
        if slug:
            encontrados[slug] = nome
    return encontrados


def conteudo_com_hashtags(texto):
    linhas = []
    for linha in (texto or "").splitlines():
        partes = []
        inicio = 0
        for correspondencia in LINK_OU_HASHTAG_RE.finditer(linha):
            partes.append(urlize(linha[inicio:correspondencia.start()], nofollow=True, autoescape=True))
            trecho = correspondencia.group(0)
            if trecho.startswith("#"):
                slug = slugify(trecho[1:])
                if slug:
                    url = reverse("posts:hashtag", kwargs={"slug": slug})
                    partes.append(format_html_link(url, trecho))
                else:
                    partes.append(escape(trecho))
            else:
                partes.append(urlize(trecho, nofollow=True, autoescape=True))
            inicio = correspondencia.end()
        partes.append(urlize(linha[inicio:], nofollow=True, autoescape=True))
        linhas.append("".join(partes))
    return mark_safe("<br>".join(linhas))


def format_html_link(url, texto):
    return mark_safe(f'<a class="hashtag-link" href="{escape(url)}">{escape(texto)}</a>')


def posts_para_exibir(queryset, usuario, incluir_comentarios=True):
    entradas = list(
        queryset.select_related("autor", "autor__perfil")
    )
    if not entradas:
        return entradas

    originais_ids = {entrada.original_id or entrada.pk for entrada in entradas}
    curtida_do_usuario = Post.curtidas.through.objects.filter(
        post_id=OuterRef("pk"), user_id=usuario.pk
    )
    republicacao_do_usuario = Post.objects.filter(
        original_id=OuterRef("pk"), autor_id=usuario.pk
    )
    salvo_pelo_usuario = Post.salvos_por.through.objects.filter(
        post_id=OuterRef("pk"), user_id=usuario.pk
    )
    originais = (
        Post.objects.filter(pk__in=originais_ids)
        .select_related("autor", "autor__perfil")
        .prefetch_related("imagens_adicionais")
        .annotate(
            total_curtidas=Count("curtidas", distinct=True),
            total_republicacoes=Count("republicacoes", distinct=True),
            total_comentarios=Count("comentarios", distinct=True),
            curtido_pelo_usuario=Exists(curtida_do_usuario),
            republicado_pelo_usuario=Exists(republicacao_do_usuario),
            salvo_pelo_usuario=Exists(salvo_pelo_usuario),
        )
    )
    if incluir_comentarios:
        curtida_em_comentario = Comentario.curtidas.through.objects.filter(
            comentario_id=OuterRef("pk"), user_id=usuario.pk
        )
        respostas = (
            Comentario.objects.select_related("autor", "autor__perfil")
            .annotate(
                total_curtidas=Count("curtidas", distinct=True),
                curtido_pelo_usuario=Exists(curtida_em_comentario),
            )
            .order_by("criado_em", "pk")
        )
        comentarios = (
            Comentario.objects.filter(resposta_para__isnull=True)
            .select_related("autor", "autor__perfil")
            .annotate(
                total_curtidas=Count("curtidas", distinct=True),
                curtido_pelo_usuario=Exists(curtida_em_comentario),
            )
            .prefetch_related(Prefetch("respostas", queryset=respostas))
            .order_by("criado_em", "pk")
        )
        originais = originais.prefetch_related(
            Prefetch("comentarios", queryset=comentarios, to_attr="comentarios_raiz")
        )
    originais = {post.pk: post for post in originais}

    for entrada in entradas:
        entrada.post_original = originais[entrada.original_id or entrada.pk]
        entrada.post_original.conteudo_formatado = conteudo_com_hashtags(
            entrada.post_original.conteudo
        )

    return entradas
