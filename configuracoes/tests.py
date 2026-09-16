import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from mensagens.models import Conversa, Mensagem
from notificacoes.models import Notificacao
from notificacoes.services import notificar
from outbox.models import EventoOutbox
from posts.models import Comentario, ImagemPost, Post, PostSemInteresse, UsuarioBloqueado, UsuarioSilenciado
from profile.models import Perfil
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
            {"username": "caua_novo", "email": self.caua.email, "senha_atual": "Senha!Forte123"},
        )
        self.assertRedirects(resposta, reverse("configuracoes:secao", args=["conta"]))
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.username, "caua_novo")
        self.assertTrue(self.caua.is_active)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_vazio_preserva_o_email_atual(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua_novo", "email": "", "senha_atual": "Senha!Forte123"},
        )
        self.assertRedirects(resposta, reverse("configuracoes:secao", args=["conta"]))
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.email, "caua@example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_proprio_email_atual_nao_gera_erro_de_unicidade(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua", "email": "CAUA@example.com", "senha_atual": "Senha!Forte123"},
        )
        self.assertRedirects(resposta, reverse("configuracoes:secao", args=["conta"]))

    def test_rejeita_username_e_email_de_outro_usuario(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": " ANA ", "email": "ANA@example.com", "senha_atual": "Senha!Forte123"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Este usuário já está em uso.")
        self.assertContains(resposta, "Este e-mail já está em uso.")

    def test_troca_de_email_exige_nova_verificacao(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua", "email": "novo@example.com", "senha_atual": "Senha!Forte123"},
        )
        self.assertRedirects(resposta, reverse("verificar_email"))
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.email, "novo@example.com")
        self.assertFalse(self.caua.is_active)
        self.assertEqual(mail.outbox[-1].to, ["novo@example.com"])

    def test_senha_atual_incorreta_impede_alteracao_de_username(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "nao_salvar", "email": self.caua.email, "senha_atual": "errada"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Senha atual incorreta.")
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.username, "caua")

    def test_senha_atual_incorreta_impede_alteracao_e_verificacao_de_email(self):
        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"username": "caua", "email": "novo@example.com", "senha_atual": "errada"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Senha atual incorreta.")
        self.caua.refresh_from_db()
        self.assertEqual(self.caua.email, "caua@example.com")
        self.assertTrue(self.caua.is_active)
        self.assertEqual(len(mail.outbox), 0)

    def test_aba_perfil_nao_existe_e_editor_original_continua_acessivel(self):
        conta = self.client.get(reverse("configuracoes:inicio"))
        self.assertNotContains(conta, "/configuracoes/perfil/")
        self.assertNotContains(conta, 'name="nome"')
        self.assertEqual(
            self.client.get(reverse("configuracoes:secao", args=["perfil"])).status_code,
            404,
        )
        self.assertEqual(self.client.get(reverse("profile:editar")).status_code, 200)

    def test_abas_privacidade_e_mensagens_existem_sem_opcoes_duplicadas(self):
        conta = self.client.get(reverse("configuracoes:inicio"))
        privacidade = self.client.get(reverse("configuracoes:secao", args=["privacidade"]))
        mensagens = self.client.get(reverse("configuracoes:secao", args=["mensagens"]))

        self.assertContains(conta, reverse("configuracoes:secao", args=["privacidade"]))
        self.assertContains(conta, reverse("configuracoes:secao", args=["mensagens"]))
        self.assertNotContains(privacidade, 'name="permitir_novas_conversas"')
        self.assertNotContains(privacidade, 'name="mensagens_de"')
        self.assertContains(mensagens, 'name="permitir_novas_conversas"')
        self.assertContains(mensagens, 'name="mensagens_de"')

    def test_seguranca_aponta_para_fluxo_existente_de_senha(self):
        resposta = self.client.get(reverse("configuracoes:secao", args=["seguranca"]))
        self.assertContains(resposta, reverse("login:password_reset"))
        self.assertContains(resposta, "Alterar senha")
        self.assertNotContains(resposta, 'name="old_password"')

    def test_desativacao_exige_confirmacao_exata(self):
        url = reverse("configuracoes:secao", args=["conta"])
        self.client.post(
            url,
            {"acao": "desativar", "confirmacao": "errado", "senha": "Senha!Forte123"},
        )
        self.caua.refresh_from_db()
        self.assertTrue(self.caua.is_active)

    def test_desativacao_exige_senha_atual_correta(self):
        url = reverse("configuracoes:secao", args=["conta"])
        post = Post.objects.create(autor=self.caua, conteudo="Preservar")
        self.client.post(
            url,
            {"acao": "desativar", "confirmacao": "caua", "senha": "errada"},
        )
        self.caua.refresh_from_db()
        self.assertTrue(self.caua.is_active)

        self.client.post(
            url,
            {"acao": "desativar", "confirmacao": "caua", "senha": "Senha!Forte123"},
        )
        self.caua.refresh_from_db()
        preferencias = PreferenciasUsuario.objects.get(usuario=self.caua)
        self.assertFalse(self.caua.is_active)
        self.assertIsNotNone(preferencias.desativada_em)
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_desativacao_preserva_dados_sociais(self):
        perfil = Perfil.objects.create(usuario=self.caua, biografia="Continuo aqui")
        perfil.seguindo.add(self.ana)
        post = Post.objects.create(autor=self.caua, conteudo="Preservar publicação")
        comentario = Comentario.objects.create(
            post=post,
            autor=self.ana,
            conteudo="Preservar comentário",
        )
        conversa = Conversa.objects.create()
        conversa.participantes.add(self.caua, self.ana)
        mensagem = Mensagem.objects.create(
            conversa=conversa,
            autor=self.ana,
            conteudo="Preservar mensagem",
        )
        notificacao = Notificacao.objects.create(
            usuario=self.caua,
            autor=self.ana,
            tipo="comentario",
            post=post,
            comentario=comentario,
        )

        self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"acao": "desativar", "confirmacao": "caua", "senha": "Senha!Forte123"},
        )

        self.assertTrue(Perfil.objects.filter(pk=perfil.pk, seguindo=self.ana).exists())
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        self.assertTrue(Comentario.objects.filter(pk=comentario.pk).exists())
        self.assertTrue(Conversa.objects.filter(pk=conversa.pk).exists())
        self.assertTrue(Mensagem.objects.filter(pk=mensagem.pk).exists())
        self.assertTrue(Notificacao.objects.filter(pk=notificacao.pk).exists())

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

    def test_exclusao_remove_conversas_um_para_um(self):
        conversa = Conversa.objects.create()
        conversa.participantes.add(self.caua, self.ana)
        Mensagem.objects.create(conversa=conversa, autor=self.caua, conteudo="Oi")

        resposta = self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"acao": "excluir_conta", "confirmacao": "caua", "senha": "Senha!Forte123"},
        )

        self.assertRedirects(resposta, reverse("cadastro"))
        self.assertFalse(Conversa.objects.filter(pk=conversa.pk).exists())

    def test_exclusao_remove_dados_relacionados_e_notificacoes(self):
        perfil = Perfil.objects.create(usuario=self.caua)
        post = Post.objects.create(autor=self.caua, conteudo="Remover")
        comentario = Comentario.objects.create(
            post=post,
            autor=self.ana,
            conteudo="Também será removido com o post",
        )
        notificacao_recebida = Notificacao.objects.create(
            usuario=self.caua,
            autor=self.ana,
            tipo="comentario",
            post=post,
            comentario=comentario,
        )
        notificacao_enviada = Notificacao.objects.create(
            usuario=self.ana,
            autor=self.caua,
            tipo="repost",
            post=post,
        )

        self.client.post(
            reverse("configuracoes:secao", args=["conta"]),
            {"acao": "excluir_conta", "confirmacao": "caua", "senha": "Senha!Forte123"},
        )

        self.assertFalse(User.objects.filter(pk=self.caua.pk).exists())
        self.assertFalse(Perfil.objects.filter(pk=perfil.pk).exists())
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())
        self.assertFalse(Comentario.objects.filter(pk=comentario.pk).exists())
        self.assertFalse(Notificacao.objects.filter(pk=notificacao_recebida.pk).exists())
        self.assertFalse(Notificacao.objects.filter(pk=notificacao_enviada.pk).exists())

    def test_desativacao_nao_remove_arquivos_e_exclusao_remove(self):
        with tempfile.TemporaryDirectory() as pasta:
            with override_settings(MEDIA_ROOT=pasta):
                perfil = Perfil.objects.create(usuario=self.caua)
                perfil.foto = SimpleUploadedFile("foto.webp", b"foto")
                perfil.banner = SimpleUploadedFile("banner.webp", b"banner")
                perfil.save(update_fields=["foto", "banner"])
                post = Post.objects.create(
                    autor=self.caua,
                    conteudo="Com mídia",
                    imagem=SimpleUploadedFile("post.webp", b"post"),
                    audio=SimpleUploadedFile("post.mp3", b"audio"),
                )
                extra = ImagemPost.objects.create(
                    post=post,
                    imagem=SimpleUploadedFile("extra.webp", b"extra"),
                )
                comentario = Comentario.objects.create(
                    post=post,
                    autor=self.ana,
                    conteudo="Comentário",
                    imagem=SimpleUploadedFile("comentario.webp", b"comentario"),
                    audio=SimpleUploadedFile("comentario.mp3", b"audio"),
                )
                nomes = [
                    perfil.foto.name,
                    perfil.banner.name,
                    post.imagem.name,
                    post.audio.name,
                    extra.imagem.name,
                    comentario.imagem.name,
                    comentario.audio.name,
                ]

                self.client.post(
                    reverse("configuracoes:secao", args=["conta"]),
                    {"acao": "desativar", "confirmacao": "caua", "senha": "Senha!Forte123"},
                )
                for nome in nomes:
                    self.assertTrue((Path(pasta) / nome).exists())

                self.caua.is_active = True
                self.caua.save(update_fields=["is_active"])
                preferencias = PreferenciasUsuario.objects.get(usuario=self.caua)
                preferencias.desativada_em = None
                preferencias.save(update_fields=["desativada_em"])
                self.client.force_login(self.caua)

                self.client.post(
                    reverse("configuracoes:secao", args=["conta"]),
                    {"acao": "excluir_conta", "confirmacao": "caua", "senha": "Senha!Forte123"},
                )

                for nome in nomes:
                    self.assertFalse((Path(pasta) / nome).exists())

    def test_exclusao_usa_storage_do_campo_sem_servico_externo_real(self):
        perfil = Perfil.objects.create(
            usuario=self.caua,
            foto="fotos_perfil/foto.webp",
            banner="banners_perfil/banner.webp",
        )
        post = Post.objects.create(
            autor=self.caua,
            conteudo="Mídias",
            imagem="imagens_posts/post.webp",
            audio="audios_posts/post.mp3",
        )
        ImagemPost.objects.create(post=post, imagem="imagens_posts/extra.webp")
        Comentario.objects.create(
            post=post,
            autor=self.ana,
            conteudo="Comentário",
            imagem="imagens_comentarios/comentario.webp",
            audio="audios_comentarios/comentario.mp3",
        )
        storage = perfil.foto.storage

        with patch.object(storage, "delete") as excluir:
            self.client.post(
                reverse("configuracoes:secao", args=["conta"]),
                {"acao": "excluir_conta", "confirmacao": "caua", "senha": "Senha!Forte123"},
            )

        self.assertCountEqual(
            [chamada.args[0] for chamada in excluir.call_args_list],
            [
                "fotos_perfil/foto.webp",
                "banners_perfil/banner.webp",
                "imagens_posts/post.webp",
                "audios_posts/post.mp3",
                "imagens_posts/extra.webp",
                "imagens_comentarios/comentario.webp",
                "audios_comentarios/comentario.mp3",
            ],
        )

    def test_exclusao_nao_remove_arquivo_compartilhado(self):
        Post.objects.create(
            autor=self.caua,
            conteudo="Original",
            imagem="imagens_posts/compartilhada.webp",
        )
        outro = Post.objects.create(
            autor=self.ana,
            conteudo="Outra referência",
            imagem="imagens_posts/compartilhada.webp",
        )

        with patch.object(outro.imagem.storage, "delete") as excluir:
            self.client.post(
                reverse("configuracoes:secao", args=["conta"]),
                {"acao": "excluir_conta", "confirmacao": "caua", "senha": "Senha!Forte123"},
            )

        excluir.assert_not_called()

    def test_falha_no_storage_nao_deixa_conta_fantasma_na_sessao(self):
        perfil = Perfil.objects.create(
            usuario=self.caua,
            foto="fotos_perfil/foto.webp",
        )

        with self.assertLogs("outbox.services", level="WARNING"):
            with patch.object(
                perfil.foto.storage,
                "delete",
                side_effect=OSError("storage fora"),
            ):
                resposta = self.client.post(
                    reverse("configuracoes:secao", args=["conta"]),
                    {
                        "acao": "excluir_conta",
                        "confirmacao": "caua",
                        "senha": "Senha!Forte123",
                    },
                )

        self.assertRedirects(resposta, reverse("cadastro"))
        self.assertFalse(User.objects.filter(pk=self.caua.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        evento = EventoOutbox.objects.get(tipo="storage.excluir")
        self.assertIsNone(evento.processado_em)
        self.assertIsNone(evento.descartado_em)
        self.assertGreater(evento.tentativas, 0)
        self.assertIn("storage fora", evento.ultimo_erro)

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

    def test_preferencias_de_mensagens_persistem_e_bloqueiam_nova_conversa(self):
        url = reverse("configuracoes:secao", args=["mensagens"])
        self.client.post(url, {"mensagens_de": "ninguem"})
        preferencias = PreferenciasUsuario.objects.get(usuario=self.caua)
        self.assertFalse(preferencias.permitir_novas_conversas)
        self.client.force_login(self.ana)
        resposta = self.client.post(reverse("mensagens:criar"), {"usuario_id": self.caua.pk})
        self.assertRedirects(resposta, reverse("profile:perfil_publico", args=[self.caua.username]))
        self.assertFalse(Conversa.objects.exists())

    def test_preferencias_salvas_na_aba_mensagens_persistem(self):
        url = reverse("configuracoes:secao", args=["mensagens"])

        resposta = self.client.post(
            url,
            {"permitir_novas_conversas": "on", "mensagens_de": "seguindo"},
        )

        self.assertRedirects(resposta, url)
        preferencias = PreferenciasUsuario.objects.get(usuario=self.caua)
        self.assertTrue(preferencias.permitir_novas_conversas)
        self.assertEqual(
            preferencias.mensagens_de,
            PreferenciasUsuario.PermissaoMensagem.SEGUINDO,
        )

    def test_preferencia_de_notificacao_impede_criacao(self):
        preferencias = self.caua.preferencias
        preferencias.notificar_curtidas = False
        preferencias.save(update_fields=["notificar_curtidas"])
        post = Post.objects.create(autor=self.caua, conteudo="Teste")
        notificar(self.caua, "curtida", self.ana, post=post)
        self.assertFalse(Notificacao.objects.exists())

    def test_privacidade_lista_apenas_contas_bloqueadas_pelo_usuario(self):
        leo = User.objects.create_user(username="leo", password="Senha!Forte123")
        UsuarioBloqueado.objects.create(usuario=self.caua, bloqueado=self.ana)
        UsuarioBloqueado.objects.create(usuario=leo, bloqueado=self.caua)

        resposta = self.client.get(reverse("configuracoes:secao", args=["privacidade"]))

        self.assertContains(resposta, "Contas bloqueadas")
        self.assertContains(resposta, "@ana")
        self.assertContains(resposta, reverse("posts:desbloquear_usuario", args=[self.ana.pk]))
        self.assertNotContains(resposta, "@leo")

    def test_conteudo_lista_silenciados_e_posts_ocultos_do_usuario(self):
        leo = User.objects.create_user(username="leo", password="Senha!Forte123")
        post_ana = Post.objects.create(autor=self.ana, conteudo="Post oculto da Ana")
        post_leo = Post.objects.create(autor=leo, conteudo="Post oculto do Leo")
        UsuarioSilenciado.objects.create(usuario=self.caua, silenciado=self.ana)
        UsuarioSilenciado.objects.create(usuario=leo, silenciado=self.caua)
        PostSemInteresse.objects.create(usuario=self.caua, post=post_ana)
        PostSemInteresse.objects.create(usuario=leo, post=post_leo)

        resposta = self.client.get(reverse("configuracoes:secao", args=["conteudo"]))

        self.assertContains(resposta, "Contas silenciadas")
        self.assertContains(resposta, "Posts ocultos")
        self.assertContains(resposta, "@ana")
        self.assertContains(resposta, "Post oculto da Ana")
        self.assertContains(resposta, reverse("posts:dessilenciar_usuario", args=[self.ana.pk]))
        self.assertContains(resposta, reverse("posts:desocultar", args=[post_ana.pk]))
        self.assertNotContains(resposta, "@leo")
        self.assertNotContains(resposta, "Post oculto do Leo")

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
