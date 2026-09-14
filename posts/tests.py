from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Comentario, Hashtag, Post


def imagem_de_teste(nome="foto.png", cor="purple"):
    dados = BytesIO()
    Image.new("RGB", (8, 8), color=cor).save(dados, format="PNG")
    return SimpleUploadedFile(nome, dados.getvalue(), content_type="image/png")


def gif_de_teste(nome="animacao.gif"):
    dados = BytesIO()
    Image.new("RGB", (8, 8), color="green").save(dados, format="GIF")
    return SimpleUploadedFile(nome, dados.getvalue(), content_type="image/gif")


class AcoesDoPostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model()
        cls.autor = usuarios.objects.create_user(username="ana", password="senha-teste")
        cls.leitor = usuarios.objects.create_user(
            username="caua", first_name="Cauã", password="senha-teste"
        )
        cls.post = Post.objects.create(autor=cls.autor, conteudo="Post original")
        cls.comentario = Comentario.objects.create(
            post=cls.post,
            autor=cls.autor,
            conteudo="Comentário inicial",
        )

    def test_curtir_e_descurtir_atualiza_o_feed(self):
        self.client.force_login(self.leitor)
        url = reverse("posts:curtir", args=[self.post.pk])

        resposta = self.client.post(url, {"return_to": "home", "entry_id": self.post.pk})

        self.assertRedirects(
            resposta, f"{reverse('home')}#post-{self.post.pk}", fetch_redirect_response=False
        )
        self.assertTrue(self.post.curtidas.filter(pk=self.leitor.pk).exists())
        feed = self.client.get(reverse("home"))
        self.assertContains(feed, 'aria-label="Descurtir"')
        self.assertContains(feed, 'aria-pressed="true"')
        self.assertEqual(feed.context["posts"][0].post_original.total_curtidas, 1)

        self.client.post(url)
        self.assertFalse(self.post.curtidas.filter(pk=self.leitor.pk).exists())
        feed = self.client.get(reverse("home"))
        self.assertContains(feed, 'aria-label="Curtir"')
        self.assertEqual(feed.context["posts"][0].post_original.total_curtidas, 0)

    def test_republicar_aparece_no_feed_e_no_perfil_e_pode_ser_desfeito(self):
        self.client.force_login(self.leitor)
        url = reverse("posts:republicar", args=[self.post.pk])

        self.client.post(url, {"return_to": "profile", "entry_id": self.post.pk})

        republicacao = Post.objects.get(autor=self.leitor, original=self.post)
        self.assertEqual(republicacao.conteudo, "")
        feed = self.client.get(reverse("home"))
        self.assertContains(feed, "Cauã republicou")
        self.assertContains(feed, "Post original", count=2)
        self.assertTrue(all(entrada.post_original.total_republicacoes == 1 for entrada in feed.context["posts"]))
        perfil = self.client.get(reverse("profile:perfil"), {"aba": "repostados"})
        self.assertContains(perfil, "Cauã republicou")
        self.assertContains(perfil, "Post original", count=1)

        self.client.post(url)
        self.assertFalse(Post.objects.filter(autor=self.leitor, original=self.post).exists())
        self.assertContains(self.client.get(reverse("profile:perfil"), {"aba": "repostados"}), "Você ainda não republicou nada")

    def test_acoes_exigem_login_e_post(self):
        for nome in ("posts:curtir", "posts:republicar"):
            url = reverse(nome, args=[self.post.pk])
            self.assertEqual(self.client.post(url).status_code, 302)
            self.client.force_login(self.leitor)
            self.assertEqual(self.client.get(url).status_code, 405)
            self.client.logout()

    def test_comentar_post_aparece_na_discussao_e_na_contagem(self):
        self.client.force_login(self.leitor)
        url = reverse("posts:comentar", args=[self.post.pk])

        resposta = self.client.post(url, {"return_to": "post", "conteudo": "Concordo plenamente!"})

        self.assertRedirects(
            resposta, reverse("posts:detalhe", args=[self.post.pk]), fetch_redirect_response=False
        )
        self.assertTrue(self.post.comentarios.filter(autor=self.leitor, conteudo="Concordo plenamente!").exists())

        feed = self.client.get(reverse("home"))
        self.assertNotContains(feed, "Concordo plenamente!")
        self.assertContains(feed, 'aria-label="Comentar"')
        self.assertEqual(feed.context["posts"][0].post_original.total_comentarios, 2)
        self.assertContains(self.client.get(reverse("posts:detalhe", args=[self.post.pk])), "Concordo plenamente!")

    def test_curtir_comentario_atualiza_contagem(self):
        self.client.force_login(self.leitor)
        url = reverse("posts:curtir_comentario", args=[self.comentario.pk])

        resposta = self.client.post(url, {"return_to": "post"})

        self.assertRedirects(
            resposta, reverse("posts:detalhe", args=[self.post.pk]), fetch_redirect_response=False
        )
        self.assertTrue(self.comentario.curtidas.filter(pk=self.leitor.pk).exists())

        discussao = self.client.get(reverse("posts:detalhe", args=[self.post.pk]))
        self.assertContains(discussao, 'aria-label="Descurtir comentário"')
        self.assertContains(discussao, ">1<")

    def test_responder_comentario_cria_resposta(self):
        self.client.force_login(self.leitor)
        url = reverse("posts:responder_comentario", args=[self.comentario.pk])

        resposta = self.client.post(
            url,
            {"return_to": "post", "conteudo": "Respondi ao comentário"},
        )

        self.assertRedirects(
            resposta, reverse("posts:detalhe", args=[self.post.pk]), fetch_redirect_response=False
        )
        self.assertTrue(
            self.comentario.respostas.filter(autor=self.leitor, conteudo="Respondi ao comentário").exists()
        )

    def test_responder_comentario_com_gif(self):
        self.client.force_login(self.leitor)

        resposta = self.client.post(
            reverse("posts:responder_comentario", args=[self.comentario.pk]),
            {"imagem": gif_de_teste()},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.json(), {"created": True})
        nova_resposta = self.comentario.respostas.get(autor=self.leitor)
        self.assertTrue(nova_resposta.imagem.name.endswith(".gif"))

    def test_resposta_nao_aparece_como_comentario_principal(self):
        resposta = Comentario.objects.create(
            post=self.post,
            autor=self.leitor,
            resposta_para=self.comentario,
            conteudo="Uma resposta",
        )

        self.client.force_login(self.leitor)
        feed = self.client.get(reverse("posts:detalhe", args=[self.post.pk]))

        self.assertContains(feed, "Comentário inicial", count=1)
        self.assertContains(feed, "Uma resposta", count=1)
        self.assertEqual(feed.context["post"].post_original.comentarios_raiz, [self.comentario])
        self.assertEqual(self.comentario.respostas.get(), resposta)

    def test_feed_aponta_para_tela_de_discussao(self):
        self.client.force_login(self.leitor)

        feed = self.client.get(reverse("home"))

        self.assertContains(feed, reverse("posts:detalhe", args=[self.post.pk]))
        self.assertNotContains(feed, "Comentário inicial")

    def test_comentario_maior_que_o_limite_nao_e_criado(self):
        self.client.force_login(self.leitor)

        self.client.post(
            reverse("posts:comentar", args=[self.post.pk]),
            {"conteudo": "a" * 281},
        )

        self.assertEqual(self.post.comentarios.count(), 1)

    def test_autor_pode_excluir_comentario_e_suas_respostas(self):
        resposta = Comentario.objects.create(
            post=self.post,
            autor=self.leitor,
            resposta_para=self.comentario,
            conteudo="Resposta que será removida",
        )
        self.client.force_login(self.autor)

        resposta_http = self.client.post(
            reverse("posts:excluir_comentario", args=[self.comentario.pk]),
            {"return_to": "post"},
        )

        self.assertRedirects(
            resposta_http, reverse("posts:detalhe", args=[self.post.pk]), fetch_redirect_response=False
        )
        self.assertFalse(Comentario.objects.filter(pk=self.comentario.pk).exists())
        self.assertFalse(Comentario.objects.filter(pk=resposta.pk).exists())

    def test_usuario_nao_pode_excluir_comentario_de_outra_pessoa(self):
        self.client.force_login(self.leitor)

        resposta = self.client.post(reverse("posts:excluir_comentario", args=[self.comentario.pk]))

        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(Comentario.objects.filter(pk=self.comentario.pk).exists())

    def test_compartilhar_aponta_para_post_original_no_feed(self):
        self.client.force_login(self.leitor)
        self.client.post(reverse("posts:republicar", args=[self.post.pk]))

        perfil = self.client.get(reverse("profile:perfil"), {"aba": "repostados"})

        self.assertContains(perfil, f'data-share-url="/#post-{self.post.pk}"')
        self.assertContains(perfil, "Compartilhar")

    def test_excluir_original_remove_republicacoes(self):
        republicacao = Post.objects.create(autor=self.leitor, original=self.post)

        self.post.delete()

        self.assertFalse(Post.objects.filter(pk=republicacao.pk).exists())


class CriarPostComImagemTests(TestCase):
    def setUp(self):
        pasta = TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        configuracao = override_settings(MEDIA_ROOT=pasta.name)
        configuracao.enable()
        self.addCleanup(configuracao.disable)

    @classmethod
    def setUpTestData(cls):
        cls.autor = get_user_model().objects.create_user(username="ana", password="senha-teste")

    def test_publicar_com_texto_e_imagem(self):
        self.client.force_login(self.autor)

        self.client.post(reverse("home"), {"conteudo": "Olha essa foto", "imagem": imagem_de_teste()})

        post = Post.objects.get(conteudo="Olha essa foto")
        self.assertTrue(post.imagem.name.startswith("imagens_posts/"))
        self.assertTrue(post.imagem.storage.exists(post.imagem.name))
        feed = self.client.get(reverse("home"))
        self.assertContains(feed, post.imagem.url)
        self.assertContains(feed, "Olha essa foto")

    def test_publicar_so_com_imagem(self):
        self.client.force_login(self.autor)

        self.client.post(reverse("home"), {"imagem": imagem_de_teste()})

        post = Post.objects.get(autor=self.autor)
        self.assertEqual(post.conteudo, "")
        self.assertTrue(post.imagem.name.startswith("imagens_posts/"))

    def test_publicar_gif(self):
        self.client.force_login(self.autor)

        self.client.post(reverse("home"), {"imagem": gif_de_teste()})

        post = Post.objects.get(autor=self.autor)
        self.assertTrue(post.imagem.name.endswith(".gif"))

    def test_publicar_varias_imagens_exibe_todas_no_feed_e_repost(self):
        self.client.force_login(self.autor)
        response = self.client.post(reverse("home"), {
            "imagem": [imagem_de_teste(), imagem_de_teste(), imagem_de_teste()],
        })
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get(autor=self.autor)
        self.assertEqual(post.imagens_adicionais.count(), 2)
        outro = get_user_model().objects.create_user(username="repostador")
        Post.objects.create(autor=outro, original=post)
        feed = self.client.get(reverse("home"))
        for foto in [post.imagem, *[item.imagem for item in post.imagens_adicionais.all()]]:
            self.assertTrue(foto.storage.exists(foto.name))
            self.assertContains(feed, foto.url, count=4)
        self.assertContains(feed, 'class="post-carousel"', count=2)
        for url in [reverse("profile:perfil"), reverse("profile:perfil_publico", args=[self.autor.username])]:
            if url != reverse("profile:perfil"):
                self.client.force_login(outro)
            response = self.client.get(url, {"aba": "midia"})
            self.assertContains(response, 'class="profile-media-item"', count=3)
            self.assertEqual(response.context["total_midia"], 3)
            for indice, foto in enumerate(post.fotos, start=1):
                self.assertContains(response, foto.url)
                self.assertContains(response, f'?foto={indice}')

    def test_uma_imagem_invalida_rejeita_o_conjunto_inteiro(self):
        self.client.force_login(self.autor)
        response = self.client.post(reverse("home"), {
            "conteudo": "Meu texto",
            "imagem": [SimpleUploadedFile("fake.png", b"invalida", content_type="image/png"), imagem_de_teste()],
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.exists())
        self.assertTrue(response.context["formulario"].errors)
        self.assertContains(response, "Meu texto")

    def test_imagem_grande_nao_e_salva(self):
        self.client.force_login(self.autor)

        arquivo = SimpleUploadedFile(
            "grande.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png"
        )

        self.client.post(reverse("home"), {"imagem": arquivo})

        self.assertFalse(Post.objects.exists())

    def test_arquivo_que_nao_e_imagem_nao_e_salvo(self):
        self.client.force_login(self.autor)

        self.client.post(
            reverse("home"),
            {"imagem": SimpleUploadedFile("fake.png", b"nao e imagem", content_type="image/png")},
        )

        self.assertFalse(Post.objects.exists())

    def test_post_so_com_texto_continua_funcionando(self):
        self.client.force_login(self.autor)

        self.client.post(reverse("home"), {"conteudo": "Só texto"})

        self.assertTrue(Post.objects.filter(conteudo="Só texto").exists())

    def test_post_vazio_nao_e_criado(self):
        self.client.force_login(self.autor)

        self.client.post(reverse("home"), {"conteudo": "   "})

        self.assertFalse(Post.objects.exists())


class HashtagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.autor = get_user_model().objects.create_user(username="ana", password="senha-teste")

    def test_publicar_indexa_hashtags_e_cria_links_no_feed(self):
        self.client.force_login(self.autor)

        self.client.post(reverse("home"), {"conteudo": "Aprendendo #Django e #web"})

        post = Post.objects.get(autor=self.autor)
        self.assertSetEqual(set(post.hashtags.values_list("slug", flat=True)), {"django", "web"})
        feed = self.client.get(reverse("home"))
        self.assertContains(feed, reverse("posts:hashtag", args=["django"]))
        self.assertContains(feed, "#Django")

    def test_pagina_de_hashtag_filtra_posts(self):
        post = Post.objects.create(autor=self.autor, conteudo="Post com #python")
        Post.objects.create(autor=self.autor, conteudo="Outro assunto")
        self.client.force_login(self.autor)

        resposta = self.client.get(reverse("posts:hashtag", args=["python"]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Post com ")
        self.assertContains(resposta, "#python")
        self.assertEqual(len(resposta.context["posts"]), 1)
        self.assertEqual(resposta.context["hashtag"].slug, "python")

    def test_hashtag_inexistente_retorna_404(self):
        self.client.force_login(self.autor)

        resposta = self.client.get(reverse("posts:hashtag", args=["nao-existe"]))

        self.assertEqual(resposta.status_code, 404)

    def test_hashtag_em_resposta_aparece_na_lista_do_post(self):
        post = Post.objects.create(autor=self.autor, conteudo="Post original")
        self.client.force_login(self.autor)

        self.client.post(
            reverse("posts:comentar", args=[post.pk]),
            {"conteudo": "Resposta com #resposta"},
        )

        resposta = self.client.get(reverse("posts:hashtag", args=["resposta"]))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([item.pk for item in resposta.context["posts"]], [post.pk])
        home = self.client.get(reverse("home"))
        self.assertContains(home, "#resposta")
        self.assertContains(home, "1 uso")


class EditarPostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model()
        cls.autor = usuarios.objects.create_user(username="ana", password="senha-teste")
        cls.outro_usuario = usuarios.objects.create_user(username="caua", password="senha-teste")
        cls.post = Post.objects.create(autor=cls.autor, conteudo="Texto antigo")

    def test_autor_pode_editar_post(self):
        self.client.force_login(self.autor)

        resposta = self.client.post(
            reverse("posts:editar", args=[self.post.pk]),
            {"conteudo": "Texto novo #atualizado"},
        )

        self.assertRedirects(resposta, reverse("home"), fetch_redirect_response=False)
        self.post.refresh_from_db()
        self.assertEqual(self.post.conteudo, "Texto novo #atualizado")
        self.assertTrue(self.post.hashtags.filter(slug="atualizado").exists())

    def test_outro_usuario_nao_pode_editar_post(self):
        self.client.force_login(self.outro_usuario)

        resposta = self.client.get(reverse("posts:editar", args=[self.post.pk]))

        self.assertEqual(resposta.status_code, 404)

    def test_botao_de_edicao_aparece_apenas_para_autor(self):
        self.client.force_login(self.autor)
        self.assertContains(self.client.get(reverse("home")), reverse("posts:editar", args=[self.post.pk]))

        self.client.force_login(self.outro_usuario)
        self.assertNotContains(self.client.get(reverse("home")), reverse("posts:editar", args=[self.post.pk]))
