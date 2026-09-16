from django.contrib.auth import get_user_model
from django.test import TestCase

from .application import ServicoRelacionamentos
from .models import Perfil


class NotificacoesFake:
    def __init__(self):
        self.enviadas = 0
        self.removidas = 0

    def enviar(self, *args, **kwargs):
        self.enviadas += 1

    def remover(self, *args, **kwargs):
        self.removidas += 1


class ServicoRelacionamentosSOLIDTests(TestCase):
    def test_follow_funciona_com_porta_de_notificacao_substituta(self):
        User = get_user_model()
        usuario = User.objects.create_user(username="solid_follow_a")
        alvo = User.objects.create_user(username="solid_follow_b")
        fake = NotificacoesFake()
        servico = ServicoRelacionamentos(fake)

        resultado = servico.definir_seguindo(usuario, alvo, True)

        self.assertTrue(resultado.permitido)
        self.assertTrue(resultado.seguindo)
        self.assertTrue(
            Perfil.objects.get(usuario=usuario).seguindo.filter(pk=alvo.pk).exists()
        )
        self.assertEqual(fake.enviadas, 1)
