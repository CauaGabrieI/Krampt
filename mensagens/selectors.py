from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce

from profile.models import Perfil

from .models import Conversa, Mensagem


User = get_user_model()


@dataclass(frozen=True)
class ListaConversas:
    conversas: list
    filtro: str
    termo_busca: str
    total_conversas: int
    total_nao_lidas: int
    total_solicitacoes: int = 0

    def as_contexto(self):
        return {
            "conversas": self.conversas,
            "filtro": self.filtro,
            "termo_busca": self.termo_busca,
            "total_conversas": self.total_conversas,
            "total_nao_lidas": self.total_nao_lidas,
            "total_solicitacoes": self.total_solicitacoes,
        }


def listar_conversas(usuario, filtro_recebido=None, termo_busca=""):
    """Read model da caixa de mensagens."""
    ultima_mensagem = Mensagem.objects.filter(
        conversa_id=OuterRef("pk")
    ).order_by("-criada_em", "-pk")

    filtro = (
        filtro_recebido
        if filtro_recebido in {"nao_lidas", "solicitacoes"}
        else "todas"
    )
    termo_busca = (termo_busca or "").strip()

    conversas = (
        Conversa.objects.filter(participantes=usuario)
        .annotate(
            ultima_id=Subquery(
                ultima_mensagem.values("pk")[:1]
            ),
            ultima_atividade=Coalesce(
                Subquery(
                    ultima_mensagem.values("criada_em")[:1]
                ),
                F("criada_em"),
            ),
            total_nao_lidas=Count(
                "mensagens",
                filter=(
                    Q(mensagens__lida=False)
                    & ~Q(mensagens__autor=usuario)
                ),
                distinct=True,
            ),
        )
        .prefetch_related(
            Prefetch(
                "participantes",
                queryset=User.objects.select_related("perfil"),
            )
        )
        .order_by("-ultima_atividade", "-pk")
    )

    total_conversas = conversas.count()
    total_nao_lidas = conversas.filter(
        total_nao_lidas__gt=0
    ).count()

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
            pk__in=[
                conversa.ultima_id
                for conversa in conversas
                if conversa.ultima_id
            ]
        ).select_related("autor")
    }

    itens = []
    for conversa in conversas:
        outra_pessoa = next(
            (
                pessoa
                for pessoa in conversa.participantes.all()
                if pessoa.pk != usuario.pk
            ),
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

    return ListaConversas(
        conversas=itens,
        filtro=filtro,
        termo_busca=termo_busca,
        total_conversas=total_conversas,
        total_nao_lidas=total_nao_lidas,
    )


def pessoas_para_nova_conversa(usuario):
    perfil = Perfil.objects.filter(usuario=usuario).first()
    if perfil is None:
        return User.objects.none()
    return perfil.seguindo.select_related("perfil").order_by("username")
