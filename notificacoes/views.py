from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET


@login_required
@require_GET
def notificacoes_view(request):
    request.user.notificacoes.filter(lida=False).update(lida=True)
    notificacoes = request.user.notificacoes.select_related(
        "autor", "autor__perfil", "post", "comentario"
    )
    return render(request, "notificacoes.html", {"notificacoes": notificacoes})