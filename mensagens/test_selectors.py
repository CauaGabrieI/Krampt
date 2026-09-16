from django.contrib.auth import get_user_model
from django.test import TestCase

from krampt.testing import QueryBudgetMixin
from profile.models import Perfil

from .models import Conversa, Mensagem
from .selectors import listar_conversas


class MensagensSelectorsQueryBudgetTests(QueryBudgetMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.usuario = User.objects.create_user(
            username="budget_msg_usuario"
        )
        Perfil.objects.create(usuario=cls.usuario)

        for indice in range(8):
            outro = User.objects.create_user(
                username=f"budget_msg_{indice}"
            )
            Perfil.objects.create(usuario=outro)
            chave = (
                f"{min(cls.usuario.pk, outro.pk)}:"
                f"{max(cls.usuario.pk, outro.pk)}"
            )
            conversa = Conversa.objects.create(chave=chave)
            conversa.participantes.add(cls.usuario, outro)
            Mensagem.objects.create(
                conversa=conversa,
                autor=outro,
                conteudo=f"Mensagem {indice}",
            )

    def test_lista_conversas_tem_orcamento_estavel(self):
        with self.assertMaxQueries(6):
            resultado = listar_conversas(
                self.usuario,
                "todas",
                "",
            )

        self.assertEqual(len(resultado.conversas), 8)
        self.assertEqual(resultado.total_conversas, 8)
        self.assertEqual(resultado.total_nao_lidas, 8)
