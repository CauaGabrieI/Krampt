from typing import Protocol


class PortaPoliticaMensagens(Protocol):
    def pode_enviar(self, remetente, destinatario) -> bool:
        ...
