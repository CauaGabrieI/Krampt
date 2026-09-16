from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from krampt.container import servico_interacoes_post
from notificacoes.models import Notificacao
from profile.models import Perfil

from .models import Comentario, Post


class AtomicidadeDeMutacoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.autor = User.objects.create_user(username="autor_atomic", password="senha")
        cls.leitor = User.objects.create_user(username="leitor_atomic", password="senha")
        cls.post = Post.objects.create(autor=cls.autor, conteudo="Post atomicidade")
        cls.comentario = Comentario.objects.create(
            post=cls.post,
            autor=cls.autor,
            conteudo="Comentário atomicidade",
        )

    def setUp(self):
        self.client.force_login(self.leitor)

    def _ajax(self, url, data):
        return self.client.post(
            url,
            data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_mesmo_like_repetido_aplica_estado_uma_vez(self):
        url = reverse("posts:curtir", args=[self.post.pk])
        self._ajax(url, {"desired_state": "1"})
        self._ajax(url, {"desired_state": "1"})

        self.assertEqual(self.post.curtidas.filter(pk=self.leitor.pk).count(), 1)
        self.assertEqual(
            Notificacao.objects.filter(
                usuario=self.autor,
                autor=self.leitor,
                tipo="curtida",
                post=self.post,
            ).count(),
            1,
        )

        self._ajax(url, {"desired_state": "0"})
        self._ajax(url, {"desired_state": "0"})
        self.assertFalse(self.post.curtidas.filter(pk=self.leitor.pk).exists())
        self.assertFalse(
            Notificacao.objects.filter(
                usuario=self.autor,
                autor=self.leitor,
                tipo="curtida",
                post=self.post,
            ).exists()
        )

    def test_mesmo_repost_repetido_nao_duplica(self):
        url = reverse("posts:republicar", args=[self.post.pk])
        self._ajax(url, {"desired_state": "1"})
        self._ajax(url, {"desired_state": "1"})

        self.assertEqual(
            Post.objects.filter(autor=self.leitor, original=self.post).count(),
            1,
        )
        self.assertEqual(
            Notificacao.objects.filter(
                usuario=self.autor,
                autor=self.leitor,
                tipo="repost",
                post=self.post,
            ).count(),
            1,
        )

    def test_mesmo_save_repetido_nao_alterna_de_volta(self):
        url = reverse("posts:salvar", args=[self.post.pk])
        self._ajax(url, {"desired_state": "1"})
        self._ajax(url, {"desired_state": "1"})
        self.assertEqual(self.post.salvos_por.filter(pk=self.leitor.pk).count(), 1)

    def test_like_de_comentario_repetido_nao_duplica(self):
        url = reverse("posts:curtir_comentario", args=[self.comentario.pk])
        self._ajax(url, {"desired_state": "1"})
        self._ajax(url, {"desired_state": "1"})

        self.assertEqual(
            self.comentario.curtidas.filter(pk=self.leitor.pk).count(),
            1,
        )
        self.assertEqual(
            Notificacao.objects.filter(
                usuario=self.autor,
                autor=self.leitor,
                tipo="curtida_comentario",
                comentario=self.comentario,
            ).count(),
            1,
        )

    def test_post_reenviado_com_mesma_chave_cria_uma_vez(self):
        dados = {
            "conteudo": "Post idempotente",
            "idempotency_key": "post-request-atomic-0001",
        }
        self.client.post(reverse("home"), dados)
        self.client.post(reverse("home"), dados)

        self.assertEqual(
            Post.objects.filter(
                autor=self.leitor,
                conteudo="Post idempotente",
            ).count(),
            1,
        )

    def test_comentario_reenviado_com_mesma_chave_cria_uma_vez(self):
        url = reverse("posts:comentar", args=[self.post.pk])
        dados = {
            "conteudo": "Comentário idempotente",
            "idempotency_key": "comment-request-atomic-0001",
        }
        self.client.post(url, dados)
        self.client.post(url, dados)

        comentarios = Comentario.objects.filter(
            autor=self.leitor,
            post=self.post,
            conteudo="Comentário idempotente",
        )
        self.assertEqual(comentarios.count(), 1)
        self.assertEqual(
            Notificacao.objects.filter(
                usuario=self.autor,
                autor=self.leitor,
                tipo="comentario",
                comentario=comentarios.get(),
            ).count(),
            1,
        )

    def test_notificacao_falhando_reverte_like(self):
        url = reverse("posts:curtir", args=[self.post.pk])
        with patch.object(
            servico_interacoes_post.notificacoes,
            "enviar",
            side_effect=RuntimeError("falha"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(url, {"desired_state": "1"})

        self.assertFalse(self.post.curtidas.filter(pk=self.leitor.pk).exists())


class AtomicidadeFollowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alvo = User.objects.create_user(username="follow_alvo", password="senha")
        cls.visitante = User.objects.create_user(username="follow_visitante", password="senha")
        Perfil.objects.create(usuario=cls.visitante)

    def setUp(self):
        self.client.force_login(self.visitante)

    def test_follow_repetido_com_mesmo_estado_nao_alterna(self):
        url = reverse("profile:seguir", args=[self.alvo.pk])
        self.client.post(url, {"desired_state": "1"})
        self.client.post(url, {"desired_state": "1"})

        perfil = Perfil.objects.get(usuario=self.visitante)
        self.assertTrue(perfil.seguindo.filter(pk=self.alvo.pk).exists())
        self.assertEqual(
            Notificacao.objects.filter(
                usuario=self.alvo,
                autor=self.visitante,
                tipo="seguidor",
            ).count(),
            1,
        )

        self.client.post(url, {"desired_state": "0"})
        self.client.post(url, {"desired_state": "0"})
        self.assertFalse(perfil.seguindo.filter(pk=self.alvo.pk).exists())
