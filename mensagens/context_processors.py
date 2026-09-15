from .models import Mensagem


def mensagens_nao_lidas(request):
    if not request.user.is_authenticated:
        return {}
    preferencias = getattr(request.user, "preferencias", None)
    if preferencias is not None and not preferencias.notificar_mensagens:
        return {"mensagens_nao_lidas": 0}

    return {
        "mensagens_nao_lidas": Mensagem.objects.filter(
            conversa__participantes=request.user, lida=False
        ).exclude(autor=request.user).count()
    }
