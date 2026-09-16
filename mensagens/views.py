from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from profile.models import Perfil
from posts.http import obter_chave_idempotencia
from krampt.container import servico_mensagens
from krampt.paginacao import parametros_sem_pagina, paginar, MENSAGENS_POR_PAGINA

from .forms import EnviarMensagemForm
from .models import Conversa, Mensagem
from .services import AVISO_MENSAGEM_BLOQUEADA

User = get_user_model()


@login_required
@require_GET
def lista_de_conversas(request):
    ultima_mensagem = Mensagem.objects.filter(conversa_id=OuterRef("pk")).order_by(
        "-criada_em", "-pk"
    )
    filtro_recebido = request.GET.get("filtro")
    filtro = filtro_recebido if filtro_recebido in {"nao_lidas", "solicitacoes"} else "todas"
    termo_busca = request.GET.get("q", "").strip()
    conversas = (
        Conversa.objects.filter(participantes=request.user)
        .annotate(
            ultima_id=Subquery(ultima_mensagem.values("pk")[:1]),
            ultima_atividade=Coalesce(
                Subquery(ultima_mensagem.values("criada_em")[:1]), F("criada_em")
            ),
            total_nao_lidas=Count(
                "mensagens",
                filter=Q(mensagens__lida=False) & ~Q(mensagens__autor=request.user),
                distinct=True,
            ),
        )
        .prefetch_related(Prefetch("participantes", queryset=User.objects.select_related("perfil")))
        .order_by("-ultima_atividade", "-pk")
    )
    total_conversas = conversas.count()
    total_nao_lidas = conversas.filter(total_nao_lidas__gt=0).count()
    if filtro == "nao_lidas":
        conversas = conversas.filter(total_nao_lidas__gt=0)
    elif filtro == "solicitacoes":
        conversas = conversas.none()
    if termo_busca:
        conversas = conversas.filter(
            Q(participantes__username__icontains=termo_busca)
            | Q(participantes__first_name__icontains=termo_busca)
            | Q(participantes__last_name__icontains=termo_busca)
            | Q(mensagens__conteudo__icontains=termo_busca)
        ).distinct()
    conversas = list(conversas)
    ultimas = {
        mensagem.pk: mensagem
        for mensagem in Mensagem.objects.filter(
            pk__in=[conversa.ultima_id for conversa in conversas if conversa.ultima_id]
        ).select_related("autor")
    }
    itens = []
    for conversa in conversas:
        outra_pessoa = next(
            (pessoa for pessoa in conversa.participantes.all() if pessoa.pk != request.user.pk),
            None,
        )
        if outra_pessoa is None:
            continue
        itens.append(
            {
                "conversa": conversa,
                "outra_pessoa": outra_pessoa,
                "ultima": ultimas.get(conversa.ultima_id),
                "nao_lidas": conversa.total_nao_lidas,
            }
        )
    return render(
        request,
        "mensagens.html",
        {
            "conversas": itens,
            "filtro": filtro,
            "termo_busca": termo_busca,
            "total_conversas": total_conversas,
            "total_nao_lidas": total_nao_lidas,
            "total_solicitacoes": 0,
        },
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
        and servico_mensagens.pode_enviar(request.user, outra_pessoa)
    )

    if request.method == "POST":
        if outra_pessoa is None:
            messages.error(request, AVISO_MENSAGEM_BLOQUEADA)
            return redirect("mensagens:detalhe", conversa_id=conversa.pk)

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
                messages.error(request, AVISO_MENSAGEM_BLOQUEADA)
                return redirect("mensagens:detalhe", conversa_id=conversa.pk)

            return redirect(
                "mensagens:detalhe",
                conversa_id=resultado.mensagem.conversa_id,
            )
    else:
        formulario = EnviarMensagemForm()

    Mensagem.objects.filter(conversa=conversa, lida=False).exclude(
        autor=request.user
    ).update(lida=True)

    pagina = paginar(
        conversa.mensagens.select_related("autor", "autor__perfil"),
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

    perfil = Perfil.objects.filter(usuario=request.user).first()
    seguindo = (
        perfil.seguindo.select_related("perfil").order_by("username")
        if perfil else User.objects.none()
    )
    return render(request, "nova_conversa.html", {"pessoas": seguindo})


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
        messages.error(request, AVISO_MENSAGEM_BLOQUEADA)
        return redirect("profile:perfil_publico", username=outra.username)

    return redirect(
        "mensagens:detalhe",
        conversa_id=resultado.conversa.pk,
    )
