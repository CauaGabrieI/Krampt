from dataclasses import dataclass

from django.db import transaction

from notificacoes.ports import PortaNotificacoes
from posts.services import bloquear_usuarios_para_mutacao, usuario_bloqueado_entre

from .models import Perfil


@dataclass(frozen=True)
class ResultadoRelacionamento:
    permitido: bool
    seguindo: bool


def _estado_final(atual: bool, desejado: bool | None) -> bool:
    return (not atual) if desejado is None else desejado


class ServicoRelacionamentos:
    def __init__(self, notificacoes: PortaNotificacoes):
        self.notificacoes = notificacoes

    def definir_seguindo(
        self,
        usuario,
        alvo,
        desejado: bool | None,
    ) -> ResultadoRelacionamento:
        if usuario.pk == alvo.pk:
            return ResultadoRelacionamento(permitido=False, seguindo=False)

        with transaction.atomic():
            bloquear_usuarios_para_mutacao(usuario, alvo)
            if usuario_bloqueado_entre(usuario, alvo):
                return ResultadoRelacionamento(permitido=False, seguindo=False)

            perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
            perfil = Perfil.objects.select_for_update().get(pk=perfil.pk)
            atual = perfil.seguindo.filter(pk=alvo.pk).exists()
            seguindo = _estado_final(atual, desejado)

            if seguindo:
                perfil.seguindo.add(alvo)
                self.notificacoes.enviar(
                    alvo,
                    "seguidor",
                    usuario,
                )
            else:
                perfil.seguindo.remove(alvo)
                self.notificacoes.remover(
                    alvo,
                    "seguidor",
                    usuario,
                )

        return ResultadoRelacionamento(permitido=True, seguindo=seguindo)
