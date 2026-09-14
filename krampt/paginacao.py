from django.core.paginator import Paginator

POSTS_POR_PAGINA = 20
MENSAGENS_POR_PAGINA = 30
NOTIFICACOES_POR_PAGINA = 30


def paginar(objetos, numero, por_pagina=POSTS_POR_PAGINA, ultima_por_padrao=False):
    """Pagina objetos e devolve a pagina correspondente.

    Listas vazias retornam a primeira (unica) pagina. Quando
    ultima_por_padrao e verdadeira e nenhum numero e informado, devolve a
    ultima pagina (conversas mostram as mensagens mais recentes).
    """
    paginador = Paginator(objetos, por_pagina)
    if ultima_por_padrao and not numero:
        return paginador.page(max(paginador.num_pages, 1))
    try:
        numero = int(numero or 1)
    except (TypeError, ValueError):
        numero = 1
    numero = min(max(numero, 1), max(1, paginador.num_pages))
    return paginador.page(numero)


def parametros_sem_pagina(request):
    """Retorna a query string atual sem o parametro page."""
    parametros = request.GET.copy()
    parametros.pop("page", None)
    return parametros.urlencode()