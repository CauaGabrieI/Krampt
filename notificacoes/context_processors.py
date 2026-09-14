def notificacoes_nao_lidas(request):
    if not request.user.is_authenticated:
        return {}
    return {"notificacoes_nao_lidas": request.user.notificacoes.filter(lida=False).count()}