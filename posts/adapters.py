from .services import comprimir_imagem_lossless


class ProcessadorImagemDjango:
    def processar(self, arquivo):
        return comprimir_imagem_lossless(arquivo)
