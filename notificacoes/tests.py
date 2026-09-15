from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from configuracoes.models import PreferenciasUsuario
from notificacoes.services import notificar
from posts.models import Comentario, Post, UsuarioBloqueado, UsuarioSilenciado
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

    def test_cabecalho_limita_badge_visual_em_99_mais(self):
        self.client.force_login(self.caua)
        for _ in range(101):
            Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="curtida", post=self.post)

        home = self.client.get(reverse("home"))

        self.assertContains(home, 'aria-label="Notificações (101 não lidas)"')
        self.assertContains(home, '<span class="header-bell-badge" aria-hidden="true">99+</span>', html=True)

    def test_pagina_lista_notificacoes_e_marca_como_lida(self):
        self.client.force_login(self.caua)
        Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="seguidor")

        pagina = self.client.get(reverse("notificacoes:lista"))

        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "começou a seguir você")
        self.assertFalse(Notificacao.objects.filter(usuario=self.caua, lida=False).exists())
        self.assertNotContains(self.client.get(reverse("home")), "header-bell-badge")

    def test_acoes_de_notificacao_marcam_todas_lidas_limpam_e_excluem_uma(self):
        self.client.force_login(self.caua)
        primeira = Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="curtida", post=self.post)
        segunda = Notificacao.objects.create(usuario=self.caua, autor=self.leo, tipo="seguidor")
        outra = Notificacao.objects.create(usuario=self.ana, autor=self.caua, tipo="seguidor")

        self.client.post(reverse("notificacoes:excluir", args=[primeira.pk]))
        self.assertFalse(Notificacao.objects.filter(pk=primeira.pk).exists())
        self.assertTrue(Notificacao.objects.filter(pk=segunda.pk).exists())
        self.assertEqual(self.client.post(reverse("notificacoes:excluir", args=[outra.pk])).status_code, 404)

        self.client.post(reverse("notificacoes:marcar_todas_como_lidas"))
        self.assertFalse(Notificacao.objects.filter(usuario=self.caua, lida=False).exists())

        self.client.post(reverse("notificacoes:limpar"))
        self.assertFalse(Notificacao.objects.filter(usuario=self.caua).exists())
        self.assertTrue(Notificacao.objects.filter(pk=outra.pk).exists())

    def test_links_de_notificacoes_apontam_para_destinos_corretos(self):
        resposta = Comentario.objects.create(
            post=self.post,
            autor=self.leo,
            resposta_para=self.comentario,
            conteudo="Resposta",
        )
        notificacoes = [
            Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="seguidor"),
            Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="curtida", post=self.post),
            Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="comentario", post=self.post, comentario=self.comentario),
            Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="resposta", post=self.post, comentario=resposta),
            Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="curtida_comentario", post=self.post, comentario=self.comentario),
            Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="repost", post=self.post),
        ]
        self.client.force_login(self.caua)

        pagina = self.client.get(reverse("notificacoes:lista"))

        self.assertContains(pagina, reverse("profile:perfil_publico", args=[self.ana.username]))
        self.assertContains(pagina, reverse("posts:detalhe", args=[self.post.pk]))
        self.assertContains(pagina, f'{reverse("posts:detalhe", args=[self.post.pk])}#comentario-{self.comentario.pk}')
        self.assertContains(pagina, f'{reverse("posts:detalhe", args=[self.post.pk])}#comentario-{resposta.pk}')
        self.assertEqual(len(notificacoes), 6)

    def test_tipo_desconhecido_nao_renderiza_como_seguidor_falso(self):
        self.client.force_login(self.caua)
        Notificacao.objects.create(usuario=self.caua, autor=self.ana, tipo="misterio")

        pagina = self.client.get(reverse("notificacoes:lista"))

        self.assertContains(pagina, "Você recebeu uma notificação.")
        self.assertNotContains(pagina, "começou a seguir você")

    def test_bloqueio_e_silencio_impedem_notificacoes_futuras(self):
        UsuarioBloqueado.objects.create(usuario=self.ana, bloqueado=self.leo)
        notificar(self.ana, "curtida", self.leo, post=self.post)
        self.assertFalse(Notificacao.objects.exists())

        UsuarioBloqueado.objects.all().delete()
        UsuarioSilenciado.objects.create(usuario=self.ana, silenciado=self.leo)
        notificar(self.ana, "curtida", self.leo, post=self.post)
        self.assertFalse(Notificacao.objects.exists())

        UsuarioSilenciado.objects.all().delete()
        notificar(self.ana, "curtida", self.leo, post=self.post)
        self.assertTrue(Notificacao.objects.filter(usuario=self.ana, autor=self.leo).exists())

    def test_bloquear_remove_notificacoes_antigas_e_desbloquear_nao_recria(self):
        Notificacao.objects.create(usuario=self.ana, autor=self.leo, tipo="curtida", post=self.post)
        Notificacao.objects.create(usuario=self.leo, autor=self.ana, tipo="seguidor")
        Notificacao.objects.create(usuario=self.caua, autor=self.leo, tipo="seguidor")
        self.client.force_login(self.ana)

        self.client.post(reverse("posts:bloquear_usuario", args=[self.leo.pk]))

        self.assertFalse(Notificacao.objects.filter(usuario=self.ana, autor=self.leo).exists())
        self.assertFalse(Notificacao.objects.filter(usuario=self.leo, autor=self.ana).exists())
        self.assertTrue(Notificacao.objects.filter(usuario=self.caua, autor=self.leo).exists())

        self.client.post(reverse("posts:desbloquear_usuario", args=[self.leo.pk]))
        self.assertFalse(Notificacao.objects.filter(usuario=self.ana, autor=self.leo).exists())
        notificar(self.ana, "curtida", self.leo, post=self.post)
        self.assertTrue(Notificacao.objects.filter(usuario=self.ana, autor=self.leo).exists())

    def test_preferencias_de_notificacao_continuam_respeitadas(self):
        preferencias = PreferenciasUsuario.objects.get(usuario=self.ana)
        tipos_e_campos = [
            ("seguidor", "notificar_seguidores"),
            ("curtida", "notificar_curtidas"),
            ("curtida_comentario", "notificar_curtidas"),
            ("comentario", "notificar_comentarios"),
            ("resposta", "notificar_respostas"),
            ("repost", "notificar_reposts"),
        ]
        for tipo, campo in tipos_e_campos:
            with self.subTest(tipo=tipo):
                setattr(preferencias, campo, False)
                preferencias.save(update_fields=[campo])
                notificar(self.ana, tipo, self.leo, post=self.post, comentario=self.comentario)
                self.assertFalse(Notificacao.objects.filter(tipo=tipo).exists())
                setattr(preferencias, campo, True)
                preferencias.save(update_fields=[campo])
                notificar(self.ana, tipo, self.leo, post=self.post, comentario=self.comentario)
                self.assertTrue(Notificacao.objects.filter(tipo=tipo).exists())
                Notificacao.objects.all().delete()

        preferencias.notificacoes_site = False
        preferencias.save(update_fields=["notificacoes_site"])
        notificar(self.ana, "curtida", self.leo, post=self.post)
        self.assertFalse(Notificacao.objects.exists())

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

    def test_abrir_pagina_marca_somente_notificacoes_exibidas_como_lidas(self):
        self.client.force_login(self.ana)

        primeira = self.client.get(reverse("notificacoes:lista"))
        ids_primeira_pagina = [notificacao.pk for notificacao in primeira.context["notificacoes"]]

        self.assertFalse(Notificacao.objects.filter(pk__in=ids_primeira_pagina, lida=False).exists())
        self.assertEqual(Notificacao.objects.filter(usuario=self.ana, lida=False).count(), 1)

        self.client.get(reverse("notificacoes:lista"), {"page": 2})
        self.assertFalse(Notificacao.objects.filter(usuario=self.ana, lida=False).exists())
