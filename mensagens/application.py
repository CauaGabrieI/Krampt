from dataclasses import dataclass

from django.db import transaction

from posts.services import bloquear_usuarios_para_mutacao

from .models import Conversa, Mensagem
from .ports import PortaPoliticaMensagens


@dataclass(frozen=True)
class ResultadoEnvioMensagem:
    permitido: bool
    mensagem: Mensagem | None = None
    duplicada: bool = False


@dataclass(frozen=True)
class ResultadoConversa:
    permitido: bool
    conversa: Conversa | None = None


class ServicoMensagens:
    def __init__(self, politica: PortaPoliticaMensagens):
        self.politica = politica

    def pode_enviar(self, remetente, destinatario) -> bool:
        return self.politica.pode_enviar(remetente, destinatario)

    def enviar(
        self,
        *,
        remetente,
        destinatario,
        conversa: Conversa,
        conteudo: str,
        chave_idempotencia: str | None,
    ) -> ResultadoEnvioMensagem:
        with transaction.atomic():
            bloquear_usuarios_para_mutacao(remetente, destinatario)

            if not self.politica.pode_enviar(remetente, destinatario):
                return ResultadoEnvioMensagem(permitido=False)

            if chave_idempotencia:
                existente = Mensagem.objects.filter(
                    autor=remetente,
                    chave_idempotencia=chave_idempotencia,
                ).first()
                if existente is not None:
                    return ResultadoEnvioMensagem(
                        permitido=True,
                        mensagem=existente,
                        duplicada=True,
                    )

            mensagem = Mensagem.objects.create(
                conversa=conversa,
                autor=remetente,
                conteudo=conteudo,
                chave_idempotencia=chave_idempotencia,
            )

        return ResultadoEnvioMensagem(
            permitido=True,
            mensagem=mensagem,
        )

    def obter_ou_criar_conversa(
        self,
        *,
        remetente,
        destinatario,
    ) -> ResultadoConversa:
        chave = self._chave_conversa(remetente, destinatario)
        existente = self._buscar_conversa_existente(
            remetente,
            destinatario,
            chave,
        )
        if existente is not None:
            return ResultadoConversa(permitido=True, conversa=existente)

        with transaction.atomic():
            bloquear_usuarios_para_mutacao(remetente, destinatario)

            existente = self._buscar_conversa_existente(
                remetente,
                destinatario,
                chave,
            )
            if existente is not None:
                return ResultadoConversa(permitido=True, conversa=existente)

            if not self.politica.pode_enviar(remetente, destinatario):
                return ResultadoConversa(permitido=False)

            conversa, criada = Conversa.objects.get_or_create(chave=chave)
            if criada:
                conversa.participantes.add(remetente, destinatario)

        return ResultadoConversa(permitido=True, conversa=conversa)

    @staticmethod
    def _chave_conversa(usuario_a, usuario_b) -> str:
        return f"{min(usuario_a.pk, usuario_b.pk)}:{max(usuario_a.pk, usuario_b.pk)}"

    @staticmethod
    def _buscar_conversa_existente(usuario_a, usuario_b, chave):
        existente = Conversa.objects.filter(chave=chave).first()
        if existente is not None:
            return existente
        return (
            Conversa.objects.filter(chave__isnull=True, participantes=usuario_a)
            .filter(participantes=usuario_b)
            .first()
        )
