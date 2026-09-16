from django.contrib.auth import get_user_model
from django.test import TestCase

from .application import ServicoMensagens
from .models import Conversa, Mensagem


class PoliticaFake:
    def __init__(self, permitido):
        self.permitido = permitido

    def pode_enviar(self, remetente, destinatario):
        return self.permitido


class ServicoMensagensSOLIDTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.remetente = User.objects.create_user(username="solid_msg_a")
        self.destinatario = User.objects.create_user(username="solid_msg_b")
        self.conversa = Conversa.objects.create(
            chave=f"{self.remetente.pk}:{self.destinatario.pk}"
        )
        self.conversa.participantes.add(self.remetente, self.destinatario)

    def test_policy_pode_ser_substituida_sem_alterar_servico(self):
        servico = ServicoMensagens(PoliticaFake(True))

        resultado = servico.enviar(
            remetente=self.remetente,
            destinatario=self.destinatario,
            conversa=self.conversa,
            conteudo="Olá",
            chave_idempotencia="solid-message-0001",
        )

        self.assertTrue(resultado.permitido)
        self.assertEqual(
            Mensagem.objects.filter(conversa=self.conversa).count(),
            1,
        )

    def test_policy_negada_impede_persistencia(self):
        servico = ServicoMensagens(PoliticaFake(False))

        resultado = servico.enviar(
            remetente=self.remetente,
            destinatario=self.destinatario,
            conversa=self.conversa,
            conteudo="Não deve gravar",
            chave_idempotencia="solid-message-0002",
        )

        self.assertFalse(resultado.permitido)
        self.assertFalse(Mensagem.objects.filter(conversa=self.conversa).exists())
