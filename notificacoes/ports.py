from typing import Protocol


class PortaNotificacoes(Protocol):
    def enviar(
        self,
        usuario,
        tipo: str,
        autor,
        *,
        post=None,
        comentario=None,
    ):
        ...

    def remover(
        self,
        usuario,
        tipo: str,
        autor,
        *,
        post=None,
        comentario=None,
    ) -> None:
        ...
