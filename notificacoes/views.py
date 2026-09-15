from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from krampt.paginacao import parametros_sem_pagina, paginar, NOTIFICACOES_POR_PAGINA
from .models import Notificacao


@login_required
@require_GET
def notificacoes_view(request):
    pagina = paginar(
        request.user.notificacoes.select_related(
            "autor", "autor__perfil", "post", "comentario"
        ),
        request.GET.get("page"),
        por_pagina=NOTIFICACOES_POR_PAGINA,
    )
    ids_exibidos = [notificacao.pk for notificacao in pagina.object_list]
    request.user.notificacoes.filter(pk__in=ids_exibidos, lida=False).update(lida=True)
    return render(
        request,
        "notificacoes.html",
        {
            "notificacoes": pagina.object_list,
            "pagina_objeto": pagina,
            "parametros_url": parametros_sem_pagina(request),
        },
    )


@login_required
@require_POST
def marcar_todas_como_lidas(request):
    request.user.notificacoes.filter(lida=False).update(lida=True)
    messages.success(request, "Todas as notificações foram marcadas como lidas.")
    return redirect("notificacoes:lista")


@login_required
@require_POST
def limpar_notificacoes(request):
    request.user.notificacoes.all().delete()
    messages.success(request, "Notificações limpas.")
    return redirect("notificacoes:lista")


@login_required
@require_POST
def excluir_notificacao(request, notificacao_id):
    notificacao = get_object_or_404(
        Notificacao.objects.filter(usuario=request.user),
        pk=notificacao_id,
    )
    notificacao.delete()
    messages.success(request, "Notificação excluída.")
    return redirect("notificacoes:lista")
