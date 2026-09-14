from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from krampt.paginacao import parametros_sem_pagina, paginar, NOTIFICACOES_POR_PAGINA


@login_required
@require_GET
def notificacoes_view(request):
    request.user.notificacoes.filter(lida=False).update(lida=True)
    pagina = paginar(
        request.user.notificacoes.select_related(
            "autor", "autor__perfil", "post", "comentario"
        ),
        request.GET.get("page"),
        por_pagina=NOTIFICACOES_POR_PAGINA,
    )
    return render(
        request,
        "notificacoes.html",
        {
            "notificacoes": pagina.object_list,
            "pagina_objeto": pagina,
            "parametros_url": parametros_sem_pagina(request),
        },
    )