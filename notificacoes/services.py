from .models import Notificacao


def notificar(usuario, tipo, autor, post=None, comentario=None):
    if usuario is None or usuario.pk == autor.pk:
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