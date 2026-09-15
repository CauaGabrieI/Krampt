from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps

from .models import Perfil

User = get_user_model()

LARGURA_BANNER = 1500


def perfil_do(usuario):
    return Perfil.objects.filter(usuario=usuario).first()


def redimensionar_banner(banner):
    imagem = ImageOps.exif_transpose(Image.open(banner))
    largura, altura = imagem.size
    if largura > LARGURA_BANNER:
        nova_altura = round(altura * LARGURA_BANNER / largura)
        imagem = imagem.resize((LARGURA_BANNER, nova_altura), Image.LANCZOS)
    if imagem.mode in {"RGBA", "LA", "P"}:
        imagem = imagem.convert("RGBA")
        fundo = Image.new("RGB", imagem.size, (27, 17, 48))
        fundo.paste(imagem, mask=imagem.split()[-1])
        imagem = fundo
    else:
        imagem = imagem.convert("RGB")
    saida = BytesIO()
    imagem.save(saida, "JPEG", quality=85)
    return ContentFile(saida.getvalue(), name="banner.jpg")


def seguindo_ids(usuario):
    perfil = perfil_do(usuario)
    if perfil is None:
        return []
    return list(perfil.seguindo.values_list("pk", flat=True))


def sugestoes_de_seguir(usuario, limite=6):
    excluidos = set(seguindo_ids(usuario))
    excluidos.add(usuario.pk)
    return list(
        User.objects.exclude(pk__in=excluidos).order_by("-date_joined", "username")[:limite]
    )


def usuarios_seguidos(usuario, limite=6):
    ids = seguindo_ids(usuario)
    if not ids:
        return []
    return list(User.objects.filter(pk__in=ids).order_by("username")[:limite])


def salvar_edicao_perfil(usuario, perfil, dados):
    foto_anterior = perfil.foto.name if perfil and perfil.foto else None
    banner_anterior = perfil.banner.name if perfil and perfil.banner else None
    with transaction.atomic():
        usuario.first_name = dados["nome"]
        usuario.save(update_fields=["first_name"])
        if perfil is None:
            perfil = Perfil(usuario=usuario)
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
    return perfil
