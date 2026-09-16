from .services import notificar, remover_notificacao


class NotificacoesDjango:
    def enviar(
        self,
        usuario,
        tipo: str,
        autor,
        *,
        post=None,
        comentario=None,
    ):
        return notificar(
            usuario,
            tipo,
            autor,
            post=post,
            comentario=comentario,
        )

    def remover(
        self,
        usuario,
        tipo: str,
        autor,
        *,
        post=None,
        comentario=None,
    ) -> None:
        remover_notificacao(
            usuario,
            tipo,
            autor,
            post=post,
            comentario=comentario,
        )
