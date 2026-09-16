from django.contrib.auth import get_user_model
from django.test import TestCase

from .application import ServicoInteracoesPost
from .models import Post


class NotificacoesFake:
    def __init__(self):
        self.enviadas = []
        self.removidas = []

    def enviar(self, usuario, tipo, autor, *, post=None, comentario=None):
        self.enviadas.append((usuario.pk, tipo, autor.pk, getattr(post, "pk", None)))

    def remover(self, usuario, tipo, autor, *, post=None, comentario=None):
        self.removidas.append((usuario.pk, tipo, autor.pk, getattr(post, "pk", None)))


class ServicoInteracoesPostSOLIDTests(TestCase):
    def test_servico_aceita_adapter_substituto_sem_depender_da_view(self):
        User = get_user_model()
        autor = User.objects.create_user(username="solid_autor")
        leitor = User.objects.create_user(username="solid_leitor")
        post = Post.objects.create(autor=autor, conteudo="SOLID")
        fake = NotificacoesFake()
        servico = ServicoInteracoesPost(fake)

        resultado = servico.curtir_post(leitor, post, True)

        self.assertTrue(resultado.ativo)
        self.assertEqual(resultado.total, 1)
        self.assertEqual(
            fake.enviadas,
            [(autor.pk, "curtida", leitor.pk, post.pk)],
        )

    def test_descurtir_usa_mesma_porta_sem_conhecer_implementacao(self):
        User = get_user_model()
        autor = User.objects.create_user(username="solid_autor_2")
        leitor = User.objects.create_user(username="solid_leitor_2")
        post = Post.objects.create(autor=autor, conteudo="SOLID 2")
        post.curtidas.add(leitor)
        fake = NotificacoesFake()
        servico = ServicoInteracoesPost(fake)

        resultado = servico.curtir_post(leitor, post, False)

        self.assertFalse(resultado.ativo)
        self.assertEqual(
            fake.removidas,
            [(autor.pk, "curtida", leitor.pk, post.pk)],
        )
