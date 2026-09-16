from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from krampt.container import servico_mensagens
from krampt.paginacao import (
    MENSAGENS_POR_PAGINA,
    paginar,
    parametros_sem_pagina,
)
from posts.http import obter_chave_idempotencia

from .forms import EnviarMensagemForm
from .models import Conversa, Mensagem
from .selectors import listar_conversas, pessoas_para_nova_conversa
from .services import AVISO_MENSAGEM_BLOQUEADA


User = get_user_model()


@login_required
@require_GET
def lista_de_conversas(request):
    resultado = listar_conversas(
        request.user,
        request.GET.get("filtro"),
        request.GET.get("q", ""),
    )
    return render(
        request,
        "mensagens.html",
        resultado.as_contexto(),
    )


@login_required
@require_http_methods(["GET", "POST"])
def conversa_view(request, conversa_id):
    conversa = get_object_or_404(
        Conversa.objects.filter(participantes=request.user),
        pk=conversa_id,
    )
    outra_pessoa = (
        conversa.participantes.exclude(pk=request.user.pk)
        .select_related("perfil")
        .first()
    )
    envio_permitido = bool(
        outra_pessoa
        and servico_mensagens.pode_enviar(
            request.user,
            outra_pessoa,
        )
    )

    if request.method == "POST":
        if outra_pessoa is None:
            messages.error(
                request,
                AVISO_MENSAGEM_BLOQUEADA,
            )
            return redirect(
                "mensagens:detalhe",
                conversa_id=conversa.pk,
            )

        formulario = EnviarMensagemForm(request.POST)
        if formulario.is_valid():
            resultado = servico_mensagens.enviar(
                remetente=request.user,
                destinatario=outra_pessoa,
                conversa=conversa,
                conteudo=formulario.cleaned_data["conteudo"],
                chave_idempotencia=obter_chave_idempotencia(request),
            )
            if not resultado.permitido:
                messages.error(
                    request,
                    AVISO_MENSAGEM_BLOQUEADA,
                )
                return redirect(
                    "mensagens:detalhe",
                    conversa_id=conversa.pk,
                )

            return redirect(
                "mensagens:detalhe",
                conversa_id=resultado.mensagem.conversa_id,
            )
    else:
        formulario = EnviarMensagemForm()

    Mensagem.objects.filter(
        conversa=conversa,
        lida=False,
    ).exclude(
        autor=request.user,
    ).update(lida=True)

    pagina = paginar(
        conversa.mensagens.select_related(
            "autor",
            "autor__perfil",
        ),
        request.GET.get("page"),
        por_pagina=MENSAGENS_POR_PAGINA,
        ultima_por_padrao=True,
    )

    return render(
        request,
        "conversa.html",
        {
            "conversa": conversa,
            "outra_pessoa": outra_pessoa,
            "envio_permitido": envio_permitido,
            "formulario": formulario,
            "mensagens": pagina.object_list,
            "pagina_objeto": pagina,
            "parametros_url": parametros_sem_pagina(request),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def nova_conversa(request):
    if request.method == "POST":
        return criar_conversa(request)

    return render(
        request,
        "nova_conversa.html",
        {
            "pessoas": pessoas_para_nova_conversa(request.user),
        },
    )


@login_required
@require_POST
def criar_conversa(request):
    usuario_id = request.POST.get("usuario_id", "")
    if not usuario_id.isascii() or not usuario_id.isdigit():
        return redirect("mensagens:lista")

    outra = get_object_or_404(User, pk=usuario_id)
    if outra.pk == request.user.pk:
        return redirect("mensagens:lista")

    resultado = servico_mensagens.obter_ou_criar_conversa(
        remetente=request.user,
        destinatario=outra,
    )
    if not resultado.permitido:
        messages.error(
            request,
            AVISO_MENSAGEM_BLOQUEADA,
        )
        return redirect(
            "profile:perfil_publico",
            username=outra.username,
        )

    return redirect(
        "mensagens:detalhe",
        conversa_id=resultado.conversa.pk,
    )
