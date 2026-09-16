from .models import Notificacao
from configuracoes.models import PreferenciasUsuario


CAMPO_POR_TIPO = {
    "seguidor": "notificar_seguidores",
    "curtida": "notificar_curtidas",
    "curtida_comentario": "notificar_curtidas",
    "comentario": "notificar_comentarios",
    "resposta": "notificar_respostas",
    "repost": "notificar_reposts",
}


def _chave_evento(usuario, tipo, autor, post=None, comentario=None):
    return (
        f"u{usuario.pk}:a{autor.pk}:t{tipo}:"
        f"p{post.pk if post is not None else 0}:"
        f"c{comentario.pk if comentario is not None else 0}"
    )


def notificar(usuario, tipo, autor, post=None, comentario=None):
    if usuario is None or usuario.pk == autor.pk:
        return None

    from posts.models import UsuarioSilenciado
    from posts.services import usuario_bloqueado_entre

    if usuario_bloqueado_entre(usuario, autor):
        return None
    if UsuarioSilenciado.objects.filter(usuario=usuario, silenciado=autor).exists():
        return None

    preferencias = PreferenciasUsuario.objects.filter(usuario=usuario).first()
    if preferencias is not None:
        campo = CAMPO_POR_TIPO.get(tipo)
        if not preferencias.notificacoes_site or (
            campo and not getattr(preferencias, campo)
        ):
            return None

    filtro = {
        "usuario": usuario,
        "tipo": tipo,
        "autor": autor,
        "post": post,
        "comentario": comentario,
    }

    # Compatibilidade com notificações anteriores à chave_evento.
    existente = Notificacao.objects.filter(**filtro).order_by("pk").first()
    if existente is not None:
        # Se houver lixo legado duplicado, ele é consolidado oportunisticamente.
        Notificacao.objects.filter(**filtro).exclude(pk=existente.pk).delete()
        return existente

    notificacao, _ = Notificacao.objects.get_or_create(
        chave_evento=_chave_evento(usuario, tipo, autor, post, comentario),
        defaults=filtro,
    )
    return notificacao


def remover_notificacao(usuario, tipo, autor, post=None, comentario=None):
    Notificacao.objects.filter(
        usuario=usuario,
        tipo=tipo,
        autor=autor,
        post=post,
        comentario=comentario,
    ).delete()
