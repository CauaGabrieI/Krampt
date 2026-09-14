from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from posts.models import Comentario, Post
from .models import Notificacao


class NotificacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.ana = user_model.objects.create_user(username="ana", first_name="Ana", password="x")
        cls.caua = user_model.objects.create_user(username="caua", first_name="Cauã", password="x")
        cls.leo = user_model.objects.create_user(username="leo", first_name="Léo", password="x")
        cls.post = Post.objects.create(autor=cls.ana, conteudo="Post da Ana")
        cls.comentario = Comentario.objects.create(post=cls.post, autor=cls.caua, conteudo="Opa")

    def test_curtida_notifica_autor_e_descurtir_remove(self):
        self.client.force_login(self.leo)
        url = reverse("posts:curtir", args=[self.post.pk])

        self.client.post(url)
        self.assertTrue(
            Notificacao.objects.filter(
                usuario=self.ana, autor=self.leo, tipo="curtida", post=self.post
            ).exists()
        )

        self.client.post(url)
        self.assertFalse(Notificacao.objects.filter(usuario=self.ana, autor=self.leo, tipo="curtida").exists())

    def test_curtir_proprio_post_nao_notifica(self):
        self.client.force_login(self.ana)

        self.client.post(reverse("posts:curtir", args=[self.post.pk]))

        self.assertFalse(Notificacao.objects.filter(usuario=self.ana, tipo="curtida").exists())

    def test_comentario_notifica_autor_do_post(self):
        self.client.force_login(self.leo)

        self.client.post(reverse("posts:comentar", args=[self.post.pk]), {"conteudo": "Comentei"})

        self.assertTrue(
            Notificacao.objects.filter(
                usuario=self.ana, autor=self.leo, tipo="comentario", post=self.post
            ).exists()
        )

    def test_excluir_comentario_remove_notificacao(self):
        self.client.force_login(self.leo)
        self.client.post(reverse("posts:comentar", args=[self.post.pk]), {"conteudo": "Comentei"})
        comentario = Comentario.objects.get(autor=self.leo)
        notificacao = Notificacao.objects.get(tipo="comentario")

        self.client.post(reverse("posts:excluir_comentario", args=[comentario.pk]))

        self.assertFalse(Notificacao.objects.filter(pk=notificacao.pk).exists())

    def test_resposta_notifica_autor_do_comentario(self):
        self.client.force_login(self.leo)

        self.client.post(
            reverse("posts:responder_comentario", args=[self.comentario.pk]),
            {"conteudo": "Resposta"},
        )

        self.assertTrue(
            Notificacao.objects.filter(
                usuario=self.caua, autor=self.leo, tipo="resposta", post=self.post
            ).exists()
        )

    def test_curtir_comentario_notifica_autor_do_comentario(self):
        self.client.force_login(self.leo)

        self.client.post(reverse("posts:curtir_comentario", args=[self.comentario.pk]))

        self.assertTrue(
            Notificacao.objects.filter(
                usuario=self.caua, autor=self.leo, tipo="curtida_comentario"
            ).exists()
        )

    def test_seguir_notifica_e_deixar_de_seguir_remove(self):
        self.client.force_login(self.leo)
        url = reverse("profile:seguir", args=[self.ana.pk])

        self.client.post(url)
        self.assertTrue(Notificacao.objects.filter(usuario=self.ana, autor=self.leo, tipo="seguidor").exists())

        self.client.post(url)
        self.assertFalse(Notificacao.objects.filter(usuario=self.ana, autor=self.leo, tipo="seguidor").exists())

    def test_pagina_exige_login(self):
        self.assertEqual(self.client.get(reverse("notificacoes:lista")).status_code, 302)

    def test_cabecalho_mostra_badge_de_nao_lidas(self):
        self.client.force_login(self.caua)
        Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="curtida", post=self.post)

        home = self.client.get(reverse("home"))

        self.assertContains(home, "header-bell-badge")
        self.assertContains(home, ">1<")

    def test_pagina_lista_notificacoes_e_marca_como_lida(self):
        self.client.force_login(self.caua)
        Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="seguidor")

        pagina = self.client.get(reverse("notificacoes:lista"))

        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "começou a seguir você")
        self.assertFalse(Notificacao.objects.filter(usuario=self.caua, lida=False).exists())
        self.assertNotContains(self.client.get(reverse("home")), "header-bell-badge")

class PaginacaoNotificacoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.ana = user_model.objects.create_user(username="ana", first_name="Ana", password="x")
        cls.caua = user_model.objects.create_user(username="caua", first_name="Cauã", password="x")
        cls.leo = user_model.objects.create_user(username="leo", first_name="Léo", password="x")
        cls.post = Post.objects.create(autor=cls.ana, conteudo="Post da Ana")
        cls.comentario = Comentario.objects.create(post=cls.post, autor=cls.caua, conteudo="Opa")
        for _ in range(31):
            Notificacao.objects.create(usuario=cls.ana, autor=cls.leo, tipo="curtida", post=cls.post)

    def test_lista_pagina_em_trinta_notificacoes(self):
        self.client.force_login(self.ana)

        primeira = self.client.get(reverse("notificacoes:lista"))

        self.assertEqual(len(primeira.context["notificacoes"]), 30)
        self.assertTrue(primeira.context["pagina_objeto"].has_next())

        segunda = self.client.get(reverse("notificacoes:lista"), {"page": 2})

        self.assertEqual(len(segunda.context["notificacoes"]), 1)
        self.assertContains(segunda, "Página 2 de 2")
