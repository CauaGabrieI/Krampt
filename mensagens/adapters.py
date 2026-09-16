from .services import pode_enviar_mensagem


class PoliticaMensagensDjango:
    def pode_enviar(self, remetente, destinatario) -> bool:
        return pode_enviar_mensagem(remetente, destinatario)
