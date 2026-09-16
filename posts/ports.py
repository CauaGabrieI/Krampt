from typing import Protocol


class PortaProcessadorImagem(Protocol):
    def processar(self, arquivo):
        ...
