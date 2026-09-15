from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notificacoes.models import Notificacao
from notificacoes.services import notificar
from profile.models import Perfil

from .models import Post, PostSemInteresse, UsuarioSilenciado


class SemanticaSocialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model()
        cls.autor = usuarios.objects.create_user(username="ana", password="senha-teste")
        cls.leitor = usuarios.objects.create_user(username="caua", password="senha-teste")
        cls.terceiro = usuarios.objects.create_user(username="leo", password="senha-teste")
        cls.post = Post.objects.create(autor=cls.autor, conteudo="Post principal da Ana")
        cls.post_terceiro = Post.objects.create(autor=cls.terceiro, conteudo="Post original do Leo")
        cls.repost_autor = Post.objects.create(autor=cls.autor, original=cls.post_terceiro)

    def test_silenciar_mantem_posts_reposts_e_follow_mas_suprime_notificacao(self):
        perfil = Perfil.objects.create(usuario=self.leitor)
        perfil.seguindo.add(self.autor)
        self.client.force_login(self.leitor)

        self.client.post(reverse("posts:silenciar_usuario", args=[self.autor.pk]))

        self.assertTrue(
            UsuarioSilenciado.objects.filter(
                usuario=self.leitor,
                silenciado=self.autor,
            ).exists()
        )
        self.assertTrue(perfil.seguindo.filter(pk=self.autor.pk).exists())

        feed = self.client.get(reverse("home"))
        self.assertContains(feed, "Post principal da Ana")
        self.assertContains(feed, "Post original do Leo")
        self.assertContains(feed, "ana republicou")

        perfil_publico = self.client.get(
            reverse("profile:perfil_publico", args=[self.autor.username])
        )
        self.assertEqual(perfil_publico.status_code, 200)
        self.assertContains(perfil_publico, "Post principal da Ana")

        notificar(self.leitor, "curtida", self.autor, post=self.post)
        self.assertFalse(
            Notificacao.objects.filter(
                usuario=self.leitor,
                autor=self.autor,
            ).exists()
        )

        self.client.post(reverse("posts:dessilenciar_usuario", args=[self.autor.pk]))
        notificar(self.leitor, "curtida", self.autor, post=self.post)
        self.assertTrue(
            Notificacao.objects.filter(
                usuario=self.leitor,
                autor=self.autor,
            ).exists()
        )

    def test_post_sem_interesse_some_do_feed_mas_continua_no_perfil_e_detalhe(self):
        PostSemInteresse.objects.create(usuario=self.leitor, post=self.post)
        self.client.force_login(self.leitor)

        self.assertNotContains(self.client.get(reverse("home")), "Post principal da Ana")

        perfil = self.client.get(
            reverse("profile:perfil_publico", args=[self.autor.username])
        )
        self.assertContains(perfil, "Post principal da Ana")

        detalhe = self.client.get(reverse("posts:detalhe", args=[self.post.pk]))
        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, "Post principal da Ana")

    def test_nao_tenho_interesse_so_aparece_em_contextos_de_feed(self):
        self.client.force_login(self.leitor)

        self.assertContains(
            self.client.get(reverse("home")),
            "Não tenho interesse neste post",
        )
        self.assertNotContains(
            self.client.get(
                reverse("profile:perfil_publico", args=[self.autor.username])
            ),
            "Não tenho interesse neste post",
        )
        self.assertNotContains(
            self.client.get(reverse("posts:detalhe", args=[self.post.pk])),
            "Não tenho interesse neste post",
        )

    def test_menu_de_silencio_nao_usa_hide_post_e_reflete_estado(self):
        self.client.force_login(self.leitor)
        mute_url = reverse("posts:silenciar_usuario", args=[self.autor.pk])
        unmute_url = reverse("posts:dessilenciar_usuario", args=[self.autor.pk])

        html = self.client.get(reverse("home")).content.decode()
        trecho = html.split(f'action="{mute_url}"', 1)[1].split("</form>", 1)[0]
        self.assertIn('data-action-type="mute-user"', trecho)
        self.assertNotIn('data-action-type="hide-post"', trecho)
        self.assertIn("Silenciar @ana", trecho)

        self.client.post(mute_url)

        html = self.client.get(reverse("home")).content.decode()
        self.assertIn(f'action="{unmute_url}"', html)
        self.assertIn("Dessilenciar @ana", html)
