from configuracoes.models import PreferenciasUsuario
from profile.models import Perfil


AVISO_MENSAGEM_BLOQUEADA = "Este usuário não está aceitando mensagens no momento."


def pode_enviar_mensagem(remetente, destinatario):
    """Avalia as preferências atuais do destinatário em cada tentativa de envio."""
    if not remetente.is_authenticated or remetente.pk == destinatario.pk:
        return False
    preferencias = PreferenciasUsuario.objects.filter(usuario=destinatario).first()
    if preferencias is None:
        return True
    if not preferencias.permitir_novas_conversas:
        return False
    if preferencias.mensagens_de == PreferenciasUsuario.PermissaoMensagem.NINGUEM:
        return False
    if preferencias.mensagens_de == PreferenciasUsuario.PermissaoMensagem.SEGUINDO:
        return Perfil.objects.filter(usuario=destinatario, seguindo=remetente).exists()
    return True
