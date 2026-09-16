from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Conversa, Mensagem


class IdempotenciaDeMensagensTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.remetente = User.objects.create_user(username="msg_remetente", password="senha")
        cls.destinatario = User.objects.create_user(username="msg_destinatario", password="senha")
        chave = f"{min(cls.remetente.pk, cls.destinatario.pk)}:{max(cls.remetente.pk, cls.destinatario.pk)}"
        cls.conversa = Conversa.objects.create(chave=chave)
        cls.conversa.participantes.add(cls.remetente, cls.destinatario)

    def setUp(self):
        self.client.force_login(self.remetente)

    def test_reenvio_da_mesma_mensagem_cria_apenas_uma_linha(self):
        url = reverse("mensagens:detalhe", args=[self.conversa.pk])
        dados = {
            "conteudo": "Mensagem exatamente uma vez",
            "idempotency_key": "message-request-atomic-0001",
        }

        self.client.post(url, dados)
        self.client.post(url, dados)

        self.assertEqual(
            Mensagem.objects.filter(
                conversa=self.conversa,
                autor=self.remetente,
                conteudo="Mensagem exatamente uma vez",
            ).count(),
            1,
        )

    def test_criacao_repetida_da_mesma_conversa_nao_duplica(self):
        url = reverse("mensagens:criar")
        self.client.post(url, {"usuario_id": self.destinatario.pk})
        self.client.post(url, {"usuario_id": self.destinatario.pk})

        self.assertEqual(
            Conversa.objects.filter(chave=self.conversa.chave).count(),
            1,
        )
