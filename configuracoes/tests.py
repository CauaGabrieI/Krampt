import json

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from mensagens.models import Conversa, Mensagem
from notificacoes.models import Notificacao
from notificacoes.services import notificar
from posts.models import Post
from .models import PreferenciasUsuario

User = get_user_model()


@override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}})
class ConfiguracoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caua = User.objects.create_user(
            username="caua", first_name="Cauã", email="caua@example.com", password="Senha!Forte123"
        )
        cls.ana = User.objects.create_user(
            username="ana", first_name="Ana", email="ana@example.com", password="Senha!Forte123"
        )

    def setUp(self):
        self.client.force_login(self.caua)

    def test_pagina_exige_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("configuracoes:inicio"))
        self.assertEqual(resposta.status_code, 302)

    def test_todas_as_secoes_abrem(self):
        for secao in ("conta", "privacidade", "mensagens", "notificacoes", "seguranca", "aparencia", "conteudo", "dados"):
            with self.subTest(secao=secao):
                resposta = self.client.get(reverse("configuracoes:secao", args=[secao]))
                self.assertEqual(resposta.status_code, 200)

    def test_salva_username_mantendo_o_proprio_email_sem_nova_verificacao(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua_novo", "email": self.caua.email},
        )
        self.assertRedirects(resposta, reverse("configuracoes:secao", args=["conta"]))
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.username, "caua_novo")
        self.assertTrue(self.caua.is_active)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_vazio_preserva_o_email_atual(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua_novo", "email": ""},
        )
        self.assertRedirects(resposta, reverse("configuracoes:secao", args=["conta"]))
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.email, "caua@example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_proprio_email_atual_nao_gera_erro_de_unicidade(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua", "email": "CAUA@example.com"},
        )
        self.assertRedirects(resposta, reverse("configuracoes:secao", args=["conta"]))

    def test_rejeita_username_e_email_de_outro_usuario(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": " ANA ", "email": "ANA@example.com"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Este usuário já está em uso.")
        self.assertContains(resposta, "Este e-mail já está em uso.")

    def test_troca_de_email_exige_nova_verificacao(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua", "email": "novo@example.com"},
        )
        self.assertRedirects(resposta, reverse("verificar_email"))
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.email, "novo@example.com")
        self.assertFalse(self.caua.is_active)
        self.assertEqual(mail.outbox[-1].to, ["novo@example.com"])

    def test_aba_perfil_nao_existe_e_editor_original_continua_acessivel(self):
        conta = self.client.get(reverse("configuracoes:inicio"))
        self.assertNotContains(conta, "/configuracoes/perfil/")
        self.assertNotContains(conta, 'name="nome"')
        self.assertEqual(
            self.client.get(reverse("configuracoes:secao", args=["perfil"])).status_code,
            404,
        )
        self.assertEqual(self.client.get(reverse("profile:editar")).status_code, 200)

    def test_seguranca_aponta_para_fluxo_existente_de_senha(self):
        resposta = self.client.get(reverse("configuracoes:secao", args=["seguranca"]))
        self.assertContains(resposta, reverse("login:password_reset"))
        self.assertContains(resposta, "Alterar senha")
        self.assertNotContains(resposta, 'name="old_password"')

    def test_desativacao_exige_confirmacao_exata(self):
        url = reverse("configuracoes:secao", args=["conta"])
        self.client.post(url, {"acao": "desativar", "confirmacao": "errado"})
        self.caua.refresh_from_db()
        self.assertTrue(self.caua.is_active)

    def test_exclusao_de_conta_exige_username_e_senha(self):
        usuario = User.objects.create_user(
            username="excluir", email="excluir@example.com", password="Senha!Forte123"
        )
        self.client.force_login(usuario)
        url = reverse("configuracoes:secao", args=["conta"])
        self.client.post(
            url,
            {"acao": "excluir_conta", "confirmacao": "excluir", "senha": "errada"},
        )
        self.assertTrue(User.objects.filter(pk=usuario.pk).exists())
        self.client.post(
            url,
            {"acao": "excluir_conta", "confirmacao": "excluir", "senha": "Senha!Forte123"},
        )
        self.assertFalse(User.objects.filter(pk=usuario.pk).exists())

    def test_sair_das_outras_sessoes_preserva_atual(self):
        outra = SessionStore()
        outra["_auth_user_id"] = str(self.caua.pk)
        outra.save()
        chave_atual = self.client.session.session_key
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["seguranca"]),
            {"acao": "sair_outras_sessoes"},
        )
        self.assertRedirects(resposta, reverse("configuracoes:secao", args=["seguranca"]))
        self.assertTrue(Session.objects.filter(session_key=chave_atual).exists())
        self.assertFalse(Session.objects.filter(session_key=outra.session_key).exists())

    def test_preferencias_de_privacidade_persistem_e_bloqueiam_nova_conversa(self):
        url = reverse("configuracoes:secao", args=["privacidade"])
        self.client.post(url, {"mensagens_de": "ninguem"})
        preferencias = PreferenciasUsuario.objects.get(usuario=self.caua)
        self.assertFalse(preferencias.permitir_novas_conversas)
        self.client.force_login(self.ana)
        resposta = self.client.post(reverse("mensagens:criar"), {"usuario_id": self.caua.pk})
        self.assertRedirects(resposta, reverse("profile:perfil_publico", args=[self.caua.username]))
        self.assertFalse(Conversa.objects.exists())

    def test_preferencia_de_notificacao_impede_criacao(self):
        preferencias = self.caua.preferencias
        preferencias.notificar_curtidas = False
        preferencias.save(update_fields=["notificar_curtidas"])
        post = Post.objects.create(autor=self.caua, conteudo="Teste")
        notificar(self.caua, "curtida", self.ana, post=post)
        self.assertFalse(Notificacao.objects.exists())

    def test_aparencia_persiste_e_rejeita_tema_invalido(self):
        url = reverse("configuracoes:secao", args=["aparencia"])
        resposta = self.client.post(
            url,
            {"tema": "claro", "tamanho_fonte": "grande", "reduzir_animacoes": "on", "densidade": "compacta"},
        )
        self.assertRedirects(resposta, url)
        self.caua.preferencias.refresh_from_db()
        self.assertEqual(self.caua.preferencias.tema, "claro")
        resposta = self.client.post(url, {"tema": "invalido", "tamanho_fonte": "padrao", "densidade": "confortavel"})
        self.assertEqual(resposta.status_code, 200)
        self.caua.preferencias.refresh_from_db()
        self.assertEqual(self.caua.preferencias.tema, "claro")

    def test_exportacao_contem_somente_dados_do_usuario(self):
        Post.objects.create(autor=self.caua, conteudo="Meu post")
        Post.objects.create(autor=self.ana, conteudo="Post alheio")
        conversa = Conversa.objects.create()
        conversa.participantes.add(self.caua, self.ana)
        Mensagem.objects.create(conversa=conversa, autor=self.caua, conteudo="Minha mensagem")
        Mensagem.objects.create(conversa=conversa, autor=self.ana, conteudo="Mensagem privada da Ana")
        resposta = self.client.get(reverse("configuracoes:exportar_dados"))
        dados = json.loads(resposta.content)
        self.assertEqual(resposta["Content-Type"], "application/json")
        self.assertEqual([post["conteudo"] for post in dados["posts"]], ["Meu post"])
        self.assertEqual([item["conteudo"] for item in dados["mensagens_enviadas"]], ["Minha mensagem"])

    def test_excluir_posts_exige_post_e_frase_exata(self):
        post = Post.objects.create(autor=self.caua, conteudo="Meu post")
        url = reverse("configuracoes:secao", args=["dados"])
        self.client.post(url, {"acao": "excluir_posts", "confirmacao": "errado"})
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        self.client.post(url, {"acao": "excluir_posts", "confirmacao": "EXCLUIR POSTS"})
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())
