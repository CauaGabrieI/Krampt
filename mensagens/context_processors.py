from .models import Mensagem


def mensagens_nao_lidas(request):
    if not request.user.is_authenticated:
        return {}

    return {
        "mensagens_nao_lidas": Mensagem.objects.filter(
            conversa__participantes=request.user, lida=False
        ).exclude(autor=request.user).count()
    }
