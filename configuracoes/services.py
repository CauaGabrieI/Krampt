import logging
import secrets
from datetime import timedelta
from hmac import compare_digest

from django.contrib.auth import get_user_model
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from login.services import _resumo
from mensagens.models import Conversa
from outbox.services import (
    enfileirar_email,
    enfileirar_exclusao_arquivos,
)
from posts.models import Comentario, ImagemPost, Post
from posts.services import suspender_limpeza_automatica_de_midias
from profile.models import Perfil

from .models import PreferenciasUsuario


logger = logging.getLogger(__name__)
User = get_user_model()

TEMPO_TOKEN_REATIVACAO = timedelta(minutes=30)
INTERVALO_REATIVACAO = timedelta(minutes=5)
JANELA_REATIVACAO = timedelta(hours=1)
LIMITE_REATIVACAO = 3


def obter_preferencias(usuario):
    return PreferenciasUsuario.objects.get_or_create(usuario=usuario)[0]


def conta_desativada_voluntariamente(usuario):
    preferencias = getattr(usuario, "preferencias", None)
    return bool(
        preferencias
        and preferencias.desativada_em
        and not usuario.is_active
    )


def desativar_conta(usuario):
    with transaction.atomic():
        usuario_bloqueado = User.objects.select_for_update().get(pk=usuario.pk)
        preferencias, _ = PreferenciasUsuario.objects.select_for_update().get_or_create(
            usuario=usuario_bloqueado
        )
        preferencias.desativada_em = timezone.now()
        preferencias.token_reativacao_hash = ""
        preferencias.token_reativacao_expira_em = None
        preferencias.save(
            update_fields=[
                "desativada_em",
                "token_reativacao_hash",
                "token_reativacao_expira_em",
            ]
        )
        usuario_bloqueado.is_active = False
        usuario_bloqueado.save(update_fields=["is_active"])
    usuario.is_active = False


def _hash_token(usuario_id, token):
    return _resumo(f"{usuario_id}:{token}", "reativacao-conta")


def _enviar_email_reativacao(
    usuario,
    request,
    token,
    *,
    chave=None,
):
    link = request.build_absolute_uri(
        reverse(
            "reativar_conta_token",
            kwargs={"token": token},
        )
    )
    contexto = {
        "usuario": usuario,
        "link": link,
        "expira_minutos": int(
            TEMPO_TOKEN_REATIVACAO.total_seconds() // 60
        ),
    }
    texto = render_to_string(
        "emails/reativacao_conta.txt",
        contexto,
    ).strip()
    html = render_to_string(
        "emails/reativacao_conta.html",
        contexto,
    ).strip()
    return enfileirar_email(
        usuario.email,
        "Reativação da sua conta Krampt",
        texto,
        html=html,
        chave=chave,
    )


@sensitive_variables("token", "token_hash")
def solicitar_reativacao(usuario, request):
    agora = timezone.now()
    with transaction.atomic():
        preferencias = (
            PreferenciasUsuario.objects.select_for_update()
            .select_related("usuario")
            .filter(usuario=usuario)
            .first()
        )
        if (
            preferencias is None
            or not preferencias.desativada_em
            or preferencias.usuario.is_active
        ):
            return "invalido"
        if (
            preferencias.reativacao_ultimo_envio_em
            and agora - preferencias.reativacao_ultimo_envio_em < INTERVALO_REATIVACAO
        ):
            return "aguarde"
        if (
            not preferencias.reativacao_janela_envio_em
            or agora - preferencias.reativacao_janela_envio_em >= JANELA_REATIVACAO
        ):
            preferencias.reativacao_janela_envio_em = agora
            preferencias.reativacao_envios_na_janela = 0
        if preferencias.reativacao_envios_na_janela >= LIMITE_REATIVACAO:
            return "limite"

        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(usuario.pk, token)

        preferencias.token_reativacao_hash = token_hash
        preferencias.token_reativacao_expira_em = agora + TEMPO_TOKEN_REATIVACAO
        preferencias.reativacao_ultimo_envio_em = agora
        preferencias.reativacao_envios_na_janela += 1
        preferencias.save(
            update_fields=[
                "token_reativacao_hash",
                "token_reativacao_expira_em",
                "reativacao_ultimo_envio_em",
                "reativacao_janela_envio_em",
                "reativacao_envios_na_janela",
            ]
        )
        _enviar_email_reativacao(
            preferencias.usuario,
            request,
            token,
            chave=(
                f"reativacao-conta:"
                f"{preferencias.usuario_id}:{token_hash}"
            ),
        )
    return "enviado"


@sensitive_variables("token", "esperado")
def reativar_por_token(token):
    agora = timezone.now()
    preferencias_qs = PreferenciasUsuario.objects.select_related("usuario").filter(
        desativada_em__isnull=False,
        token_reativacao_hash__gt="",
        token_reativacao_expira_em__gt=agora,
        usuario__is_active=False,
    )
    for preferencias in preferencias_qs:
        esperado = _hash_token(preferencias.usuario_id, token)
        if compare_digest(esperado, preferencias.token_reativacao_hash):
            with transaction.atomic():
                bloqueada = PreferenciasUsuario.objects.select_for_update().select_related("usuario").get(
                    pk=preferencias.pk
                )
                if (
                    not bloqueada.desativada_em
                    or bloqueada.usuario.is_active
                    or not bloqueada.token_reativacao_hash
                    or not bloqueada.token_reativacao_expira_em
                    or bloqueada.token_reativacao_expira_em <= timezone.now()
                    or not compare_digest(_hash_token(bloqueada.usuario_id, token), bloqueada.token_reativacao_hash)
                ):
                    return False
                bloqueada.usuario.is_active = True
                bloqueada.usuario.save(update_fields=["is_active"])
                bloqueada.desativada_em = None
                bloqueada.token_reativacao_hash = ""
                bloqueada.token_reativacao_expira_em = None
                bloqueada.reativacao_ultimo_envio_em = None
                bloqueada.reativacao_janela_envio_em = None
                bloqueada.reativacao_envios_na_janela = 0
                bloqueada.save(
                    update_fields=[
                        "desativada_em",
                        "token_reativacao_hash",
                        "token_reativacao_expira_em",
                        "reativacao_ultimo_envio_em",
                        "reativacao_janela_envio_em",
                        "reativacao_envios_na_janela",
                    ]
                )
            return True
    return False


def arquivos_da_conta(usuario):
    arquivos = []
    perfil = Perfil.objects.filter(usuario=usuario).first()
    if perfil:
        arquivos.extend([perfil.foto, perfil.banner])
    posts = Post.objects.filter(autor=usuario)
    for post in posts:
        arquivos.extend([post.imagem, post.audio])
    for imagem in ImagemPost.objects.filter(post__autor=usuario).select_related("post"):
        arquivos.append(imagem.imagem)
    comentarios = Comentario.objects.filter(autor=usuario) | Comentario.objects.filter(post__autor=usuario)
    for comentario in comentarios.distinct():
        arquivos.extend([comentario.imagem, comentario.audio])
    return [arquivo for arquivo in arquivos if arquivo and arquivo.name]


def _arquivo_tem_outro_dono(field_file, usuario_pk):
    nome = field_file.name
    if Perfil.objects.exclude(usuario_id=usuario_pk).filter(foto=nome).exists():
        return True
    if Perfil.objects.exclude(usuario_id=usuario_pk).filter(banner=nome).exists():
        return True
    if Post.objects.exclude(autor_id=usuario_pk).filter(imagem=nome).exists():
        return True
    if Post.objects.exclude(autor_id=usuario_pk).filter(audio=nome).exists():
        return True
    if ImagemPost.objects.exclude(post__autor_id=usuario_pk).filter(imagem=nome).exists():
        return True
    if Comentario.objects.exclude(autor_id=usuario_pk).exclude(post__autor_id=usuario_pk).filter(imagem=nome).exists():
        return True
    if Comentario.objects.exclude(autor_id=usuario_pk).exclude(post__autor_id=usuario_pk).filter(audio=nome).exists():
        return True
    return False


def excluir_conta_com_limpeza(usuario):
    usuario_pk = usuario.pk
    arquivos = {}
    for arquivo in arquivos_da_conta(usuario):
        chave = (id(arquivo.storage), arquivo.name)
        arquivos[chave] = (
            arquivo,
            _arquivo_tem_outro_dono(arquivo, usuario_pk),
        )

    nomes_para_excluir = [
        arquivo.name
        for arquivo, compartilhado in arquivos.values()
        if not compartilhado
    ]

    try:
        with suspender_limpeza_automatica_de_midias():
            with transaction.atomic():
                usuario_bloqueado = (
                    User.objects.select_for_update()
                    .get(pk=usuario_pk)
                )
                if nomes_para_excluir:
                    enfileirar_exclusao_arquivos(
                        nomes_para_excluir,
                        chave=f"excluir-conta:{usuario_pk}",
                    )
                Conversa.objects.filter(
                    participantes=usuario_bloqueado
                ).delete()
                usuario_bloqueado.delete()
    except Exception:
        logger.exception(
            "Falha ao excluir conta do usuário %s.",
            usuario_pk,
        )
        raise

    return ()
