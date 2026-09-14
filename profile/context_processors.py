from .services import seguindo_ids, sugestoes_de_seguir, usuarios_seguidos


def relacoes_de_seguir(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "sugestoes": sugestoes_de_seguir(request.user),
        "seguindo_usuarios": usuarios_seguidos(request.user),
        "seguindo_ids": seguindo_ids(request.user),
    }