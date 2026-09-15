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


def notificar(usuario, tipo, autor, post=None, comentario=None):
    if usuario is None or usuario.pk == autor.pk:
        return
    from posts.models import UsuarioSilenciado
    from posts.services import usuario_bloqueado_entre

    if usuario_bloqueado_entre(usuario, autor):
        return
    if UsuarioSilenciado.objects.filter(usuario=usuario, silenciado=autor).exists():
        return
    preferencias = PreferenciasUsuario.objects.filter(usuario=usuario).first()
    if preferencias is not None:
        campo = CAMPO_POR_TIPO.get(tipo)
        if not preferencias.notificacoes_site or (campo and not getattr(preferencias, campo)):
            return
    Notificacao.objects.create(
        usuario=usuario,
        tipo=tipo,
        autor=autor,
        post=post,
        comentario=comentario,
    )


def remover_notificacao(usuario, tipo, autor, post=None, comentario=None):
    Notificacao.objects.filter(
        usuario=usuario,
        tipo=tipo,
        autor=autor,
        post=post,
        comentario=comentario,
    ).delete()
