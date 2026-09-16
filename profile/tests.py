from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from posts.models import Post
from posts.models import UsuarioBloqueado
from mensagens.models import Conversa
from .models import DenunciaUsuario, Perfil


class SeguirUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.caua = user_model.objects.create_user(
            username="caua", first_name="Cauã", password="senha-teste"
        )
        cls.ana = user_model.objects.create_user(
            username="ana", first_name="Ana", password="senha-teste"
        )
        cls.leo = user_model.objects.create_user(username="leo", password="senha-teste")
        Post.objects.create(autor=cls.ana, conteudo="Post da Ana")
        Post.objects.create(autor=cls.leo, conteudo="Post do Léo")

    def test_seguir_alterna_seguir_e_deixar_de_seguir(self):
        self.client.force_login(self.caua)
        url = reverse("profile:seguir", args=[self.ana.pk])

        self.client.post(url)
        perfil = Perfil.objects.get(usuario=self.caua)
        self.assertTrue(perfil.seguindo.filter(pk=self.ana.pk).exists())

        self.client.post(url)
        perfil.refresh_from_db()
        self.assertFalse(perfil.seguindo.filter(pk=self.ana.pk).exists())

    def test_nao_pode_seguir_a_si_mesmo(self):
        self.client.force_login(self.caua)

        self.client.post(reverse("profile:seguir", args=[self.caua.pk]))

        self.assertFalse(Perfil.objects.filter(usuario=self.caua).exists())

    def test_redireciona_de_volta_para_referer_interno(self):
        self.client.force_login(self.caua)

        resposta = self.client.post(
            reverse("profile:seguir", args=[self.ana.pk]),
            HTTP_REFERER="/perfil/",
        )

        self.assertRedirects(resposta, "/perfil/", fetch_redirect_response=False)

    def test_redireciona_de_volta_para_referer_absoluto_do_mesmo_site(self):
        self.client.force_login(self.caua)

        resposta = self.client.post(
            reverse("profile:seguir", args=[self.ana.pk]),
            HTTP_REFERER="http://testserver/buscar/?q=ana",
        )

        self.assertRedirects(resposta, "http://testserver/buscar/?q=ana")

    def test_botoes_da_busca_lateral_e_perfil_usam_o_mesmo_estado(self):
        self.client.force_login(self.caua)
        busca_url = f"{reverse('buscar')}?q=ana"
        seguir_url = reverse("profile:seguir", args=[self.ana.pk])

        antes = self.client.get(busca_url)
        self.assertContains(antes, 'class="follow-button"', count=3)

        resposta = self.client.post(seguir_url, {"next": busca_url})
        self.assertRedirects(resposta, busca_url)

        busca = self.client.get(busca_url)
        self.assertContains(busca, 'class="follow-button is-following"', count=1)
        self.assertNotContains(busca, "<h2>Seguindo</h2>", html=True)
        perfil = self.client.get(reverse("profile:perfil_publico", args=[self.ana.username]))
        self.assertContains(perfil, 'class="follow-button is-following"', count=1)
        self.assertNotContains(perfil, "<h2>Seguindo</h2>", html=True)

        resposta = self.client.post(
            seguir_url,
            {"next": reverse("profile:perfil_publico", args=[self.ana.username])},
        )
        self.assertRedirects(
            resposta, reverse("profile:perfil_publico", args=[self.ana.username])
        )
        depois = self.client.get(busca_url)
        self.assertContains(depois, 'class="follow-button"', count=3)

    def test_feed_seguindo_mostra_so_o_que_autores_seguidos_publicam(self):
        self.client.force_login(self.caua)
        perfil = Perfil.objects.create(usuario=self.caua)
        perfil.seguindo.add(self.ana)

        feed = self.client.get(reverse("home"), {"filtro": "seguindo"})

        self.assertContains(feed, "Post da Ana")
        self.assertNotContains(feed, "Post do Léo")

    def test_aba_seguindo_e_recenentes_no_feed(self):
        self.client.force_login(self.caua)
        self.client.post(reverse("profile:seguir", args=[self.ana.pk]))

        feed = self.client.get(reverse("home"), {"filtro": "seguindo"})
        self.assertContains(feed, "/?filtro=seguindo")
        self.assertContains(feed, 'class="is-active">Seguindo')
        self.assertContains(feed, '>Recentes</a>')

        feed_livre = self.client.get(reverse("home"))
        self.assertContains(feed_livre, 'class="is-active">Recentes')

    def test_sugestoes_excluem_logado_e_ja_seguidos(self):
        self.client.force_login(self.caua)
        perfil = Perfil.objects.create(usuario=self.caua)
        perfil.seguindo.add(self.ana)

        feed = self.client.get(reverse("home"))

        sugestoes = feed.context["sugestoes"]
        self.assertIn(self.leo, sugestoes)
        self.assertNotIn(self.caua, sugestoes)
        self.assertNotIn(self.ana, sugestoes)

    def test_perfil_mostra_contagem_de_seguindo_e_seguidores(self):
        self.client.force_login(self.caua)
        perfil = Perfil.objects.create(usuario=self.caua)
        perfil.seguindo.add(self.ana)

        pagina = self.client.get(reverse("profile:perfil"))

        self.assertContains(pagina, ">1</strong> seguindo")
        self.assertContains(pagina, ">0</strong> seguidores")

    def test_perfil_de_outro_usuario_mostra_botao_de_mensagem(self):
        self.client.force_login(self.caua)

        pagina = self.client.get(
            reverse("profile:perfil_publico", args=[self.ana.username])
        )

        self.assertContains(pagina, 'class="profile-message-button"')
        self.assertContains(pagina, f'action="{reverse("mensagens:criar")}"')
        self.assertContains(pagina, f'name="usuario_id" value="{self.ana.pk}"')
        self.assertContains(pagina, ">chat</span>")

    def test_meu_perfil_nao_mostra_botao_de_mensagem(self):
        self.client.force_login(self.caua)

        pagina = self.client.get(reverse("profile:perfil"))

        self.assertNotContains(pagina, 'class="profile-message-button"')

    def test_botao_do_perfil_abre_a_conversa_correta_e_reutiliza_existente(self):
        self.client.force_login(self.caua)
        conversa = Conversa.objects.create(
            chave=f"{min(self.caua.pk, self.ana.pk)}:{max(self.caua.pk, self.ana.pk)}"
        )
        conversa.participantes.add(self.caua, self.ana)

        resposta = self.client.post(
            reverse("mensagens:criar"), {"usuario_id": self.ana.pk}
        )

        self.assertRedirects(
            resposta, reverse("mensagens:detalhe", args=[conversa.pk])
        )
        self.assertEqual(Conversa.objects.count(), 1)

    def test_bloqueio_impede_novo_follow_e_oculta_acoes_do_perfil(self):
        UsuarioBloqueado.objects.create(usuario=self.ana, bloqueado=self.caua)
        self.client.force_login(self.caua)

        resposta = self.client.post(reverse("profile:seguir", args=[self.ana.pk]))

        self.assertRedirects(resposta, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(Perfil.objects.filter(usuario=self.caua, seguindo=self.ana).exists())
        perfil = self.client.get(reverse("profile:perfil_publico", args=[self.ana.username]))
        resumo = perfil.content.decode().split('<div class="profile-summary-actions">', 1)[1].split("</div>", 1)[0]
        self.assertContains(perfil, "Perfil indisponível")
        self.assertNotIn('class="follow-button"', resumo)
        self.assertNotIn('class="profile-message-button"', resumo)


def foto_de_teste(nome="foto.png", cor="purple"):
    dados = BytesIO()
    Image.new("RGB", (8, 8), color=cor).save(dados, format="PNG")
    return SimpleUploadedFile(nome, dados.getvalue(), content_type="image/png")


class AbasPerfilTests(TestCase):
    def setUp(self):
        pasta = TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        configuracao = override_settings(MEDIA_ROOT=pasta.name)
        configuracao.enable()
        self.addCleanup(configuracao.disable)

        modelo_usuario = get_user_model()
        self.autor = modelo_usuario.objects.create_user(username="autor", password="senha")
        self.visitante = modelo_usuario.objects.create_user(username="visitante", password="senha")
        Post.objects.create(autor=self.autor, conteudo="Texto próprio")
        self.post_com_imagem = Post.objects.create(
            autor=self.autor, conteudo="Foto própria", imagem=foto_de_teste()
        )
        self.post_de_outro = Post.objects.create(
            autor=self.visitante, conteudo="Texto republicado"
        )
        self.republicacao = Post.objects.create(
            autor=self.autor, original=self.post_de_outro
        )

    def test_abas_do_meu_perfil_separam_publicacoes_reposts_e_midia(self):
        self.client.force_login(self.autor)
        url = reverse("profile:perfil")

        publicacoes = self.client.get(url)
        self.assertEqual(publicacoes.context["aba"], "publicacoes")
        self.assertEqual(publicacoes.context["total_posts"], 3)
        self.assertEqual(publicacoes.context["total_publicacoes"], 2)
        self.assertEqual(publicacoes.context["total_repostados"], 1)
        self.assertEqual(publicacoes.context["total_midia"], 1)
        self.assertContains(publicacoes, "Texto próprio")
        self.assertNotContains(publicacoes, "Texto republicado")
        self.assertContains(publicacoes, 'href="/perfil/?aba=repostados"')

        repostados = self.client.get(url, {"aba": "repostados"})
        self.assertEqual(repostados.context["aba"], "repostados")
        self.assertContains(repostados, "Texto republicado")
        self.assertNotContains(repostados, "Texto próprio")

        midia = self.client.get(url, {"aba": "midia"})
        self.assertEqual(midia.context["aba"], "midia")
        self.assertContains(midia, "profile-media-grid")
        self.assertContains(midia, self.post_com_imagem.imagem.url)
        self.assertContains(midia, reverse("posts:detalhe", args=[self.post_com_imagem.pk]))
        self.assertNotContains(midia, "Texto republicado")

    def test_perfil_publico_tem_as_mesmas_abas(self):
        self.client.force_login(self.visitante)
        url = reverse("profile:perfil_publico", args=[self.autor.username])

        publicacoes = self.client.get(url)
        self.assertContains(publicacoes, "Texto próprio")
        self.assertNotContains(publicacoes, "Texto republicado")

        repostados = self.client.get(url, {"aba": "repostados"})
        self.assertContains(repostados, "Texto republicado")
        self.assertNotContains(repostados, "Texto próprio")

        midia = self.client.get(url, {"aba": "midia"})
        self.assertContains(midia, self.post_com_imagem.imagem.url)
        self.assertContains(midia, "profile-media-grid")

    def test_acoes_em_repostados_voltam_para_a_aba(self):
        self.client.force_login(self.autor)
        caminho = f"{reverse('profile:perfil')}?aba=repostados"

        curtida = self.client.post(
            reverse("posts:curtir", args=[self.post_de_outro.pk]),
            {"return_path": caminho, "entry_id": self.republicacao.pk},
        )
        self.assertRedirects(
            curtida, f"{caminho}#post-{self.republicacao.pk}", fetch_redirect_response=False
        )

        exclusao = self.client.post(
            reverse("posts:excluir", args=[self.republicacao.pk]),
            {"return_path": caminho},
        )
        self.assertRedirects(exclusao, caminho)
        self.assertFalse(Post.objects.filter(pk=self.republicacao.pk).exists())


class PerfilViewTests(TestCase):
    def setUp(self):
        pasta = TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        configuracao = override_settings(MEDIA_ROOT=pasta.name)
        configuracao.enable()
        self.addCleanup(configuracao.disable)

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.usuario = user_model.objects.create_user(
            username="caua", first_name="Cauã", password="senha-teste"
        )
        outro_usuario = user_model.objects.create_user(
            username="outro", password="senha-teste"
        )
        cls.post = Post.objects.create(autor=cls.usuario, conteudo="Meu post no perfil")
        Post.objects.create(autor=outro_usuario, conteudo="Post de outra pessoa")

    def test_perfil_mostra_apenas_posts_do_usuario_logado(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("profile:perfil"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "perfil.html")
        self.assertContains(response, "Meu post no perfil")
        self.assertNotContains(response, "Post de outra pessoa")
        self.assertContains(response, reverse("posts:excluir", args=[self.post.id]), count=1)
        self.assertContains(response, "/static/css/base.css")
        self.assertContains(response, "/static/css/perfil.css")

    def test_perfil_exige_login(self):
        response = self.client.get(reverse("profile:perfil"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("next=/perfil/", response["Location"])

    def test_upload_mostra_foto_no_perfil_e_na_home(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("profile:editar"), {"nome": "Cauã", "foto": foto_de_teste()}
        )

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertTrue(perfil.foto.name.startswith("fotos_perfil/"))
        self.assertTrue(perfil.foto.storage.exists(perfil.foto.name))
        self.assertTrue(perfil.foto.url.startswith("/media/fotos_perfil/"))
        self.assertContains(self.client.get(reverse("profile:perfil")), perfil.foto.url)
        self.assertContains(self.client.get(reverse("home")), perfil.foto.url)

    def test_upload_invalido_nao_salva(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("profile:editar"),
            {"nome": "Cauã", "foto": SimpleUploadedFile("fake.png", b"nao e imagem", content_type="image/png")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["formulario"].errors)
        self.assertFalse(Perfil.objects.filter(usuario=self.usuario).exists())

    def test_foto_com_lado_acima_do_limite_e_rejeitada(self):
        self.client.force_login(self.usuario)

        larga = BytesIO()
        Image.new("RGB", (9000, 10), color="red").save(larga, format="PNG")
        response = self.client.post(
            reverse("profile:editar"),
            {
                "nome": "Cauã",
                "foto": SimpleUploadedFile("larga.png", larga.getvalue(), content_type="image/png"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["formulario"].errors)
        self.assertFalse(Perfil.objects.filter(usuario=self.usuario).exists())

    def test_troca_foto_remove_arquivo_anterior(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("profile:editar"), {"nome": "Cauã", "foto": foto_de_teste()})
        perfil = Perfil.objects.get(usuario=self.usuario)
        foto_antiga = perfil.foto.name

        response = self.client.post(
            reverse("profile:editar"), {"nome": "Cauã", "foto": foto_de_teste("nova.png", "blue")}
        )

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil.refresh_from_db()
        self.assertNotEqual(perfil.foto.name, foto_antiga)
        self.assertFalse(perfil.foto.storage.exists(foto_antiga))

    def test_perfil_sem_foto_usa_imagem_padrao(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("profile:perfil"))

        self.assertContains(response, 'class="avatar profile-avatar" src="/static/imgs/images.png"')

    def test_tela_edicao_exige_login_e_mostra_dados_atuais(self):
        url = reverse("profile:editar")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.usuario)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editar_perfil.html")
        self.assertContains(response, 'value="Cauã"')
        self.assertContains(response, "/static/css/editar_perfil.css")

    def test_edicao_atualiza_nome_bio_e_foto(self):
        self.client.force_login(self.usuario)

        response = self.client.post(reverse("profile:editar"), {
            "nome": "Cauã Silva",
            "biografia": "Criando a Krampt",
            "foto": foto_de_teste(),
        })

        self.assertRedirects(response, reverse("profile:perfil"))
        self.usuario.refresh_from_db()
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertEqual(self.usuario.first_name, "Cauã Silva")
        self.assertEqual(perfil.biografia, "Criando a Krampt")
        self.assertTrue(perfil.foto.storage.exists(perfil.foto.name))
        pagina = self.client.get(reverse("profile:perfil"))
        self.assertContains(pagina, "Cauã Silva")
        self.assertContains(pagina, "Criando a Krampt")
        self.assertContains(pagina, reverse("profile:editar"))

    def test_edicao_sem_nova_foto_mantem_a_foto_atual(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("profile:editar"), {
            "nome": "Cauã", "biografia": "Bio antiga", "foto": foto_de_teste()
        })
        foto_atual = Perfil.objects.get(usuario=self.usuario).foto.name

        response = self.client.post(reverse("profile:editar"), {
            "nome": "Novo nome", "biografia": "Bio nova"
        })

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertEqual(perfil.foto.name, foto_atual)
        self.assertEqual(perfil.biografia, "Bio nova")

    def test_edicao_pode_remover_foto(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("profile:editar"), {
            "nome": "Cauã", "foto": foto_de_teste()
        })
        perfil = Perfil.objects.get(usuario=self.usuario)
        foto_antiga = perfil.foto.name

        response = self.client.post(reverse("profile:editar"), {
            "nome": "Cauã", "biografia": "", "remover_foto": "on"
        })

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil.refresh_from_db()
        self.assertFalse(perfil.foto)
        self.assertFalse(perfil.foto.storage.exists(foto_antiga))

    def test_imagem_invalida_nao_altera_nome_ou_bio(self):
        self.client.force_login(self.usuario)

        response = self.client.post(reverse("profile:editar"), {
            "nome": "Nome alterado",
            "biografia": "Bio alterada",
            "foto": SimpleUploadedFile("fake.png", b"nao e imagem", content_type="image/png"),
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["formulario"].errors)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Cauã")
        self.assertFalse(Perfil.objects.filter(usuario=self.usuario).exists())

    def test_sem_banner_usa_capa_decorativa(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("profile:perfil"))

        self.assertContains(response, 'class="profile-cover"')
        self.assertNotContains(response, "profile-cover has-banner")

    def test_banner_salvo_e_mostrado_no_perfil(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("profile:editar"), {"nome": "Cauã", "banner": foto_de_teste("banner.png")}
        )

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertTrue(perfil.banner.name.startswith("banners_perfil/"))
        self.assertTrue(perfil.banner.storage.exists(perfil.banner.name))
        self.assertTrue(perfil.banner.url.startswith("/media/banners_perfil/"))
        pagina = self.client.get(reverse("profile:perfil"))
        self.assertContains(pagina, "profile-cover has-banner")
        self.assertContains(pagina, perfil.banner.url)
        self.assertContains(self.client.get(reverse("profile:editar")), perfil.banner.url)

    def test_edicao_sem_novo_banner_mantem_banner_atual(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("profile:editar"), {"nome": "Cauã", "banner": foto_de_teste()})
        banner_atual = Perfil.objects.get(usuario=self.usuario).banner.name

        response = self.client.post(reverse("profile:editar"), {"nome": "Novo nome"})

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertEqual(perfil.banner.name, banner_atual)
        self.assertTrue(perfil.banner.storage.exists(banner_atual))

    def test_troca_banner_remove_arquivo_anterior(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("profile:editar"), {"nome": "Cauã", "banner": foto_de_teste()})
        banner_antigo = Perfil.objects.get(usuario=self.usuario).banner.name

        response = self.client.post(
            reverse("profile:editar"), {"nome": "Cauã", "banner": foto_de_teste("novo.png", "blue")}
        )

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertNotEqual(perfil.banner.name, banner_antigo)
        self.assertFalse(perfil.banner.storage.exists(banner_antigo))

    def test_edicao_pode_remover_banner(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("profile:editar"), {"nome": "Cauã", "banner": foto_de_teste()})
        perfil_criado = Perfil.objects.get(usuario=self.usuario)
        banner_antigo = perfil_criado.banner.name

        response = self.client.post(reverse("profile:editar"), {
            "nome": "Cauã", "remover_banner": "on"
        })

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertFalse(perfil.banner)
        self.assertFalse(perfil.banner.storage.exists(banner_antigo))
        pagina = self.client.get(reverse("profile:perfil"))
        self.assertContains(pagina, 'class="profile-cover"')
        self.assertNotContains(pagina, "profile-cover has-banner")

    def test_nao_pode_enviar_e_remover_banner_ao_mesmo_tempo(self):
        self.client.force_login(self.usuario)

        response = self.client.post(reverse("profile:editar"), {
            "nome": "Cauã", "banner": foto_de_teste(), "remover_banner": "on"
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["formulario"].errors)
        self.assertFalse(Perfil.objects.filter(usuario=self.usuario).exists())

    def test_banner_grande_e_reduzido_sem_cortar(self):
        self.client.force_login(self.usuario)
        dados = BytesIO()
        Image.new("RGB", (1600, 900), color="red").save(dados, format="JPEG")
        arquivo = SimpleUploadedFile("foto.jpeg", dados.getvalue(), content_type="image/jpeg")

        response = self.client.post(reverse("profile:editar"), {"nome": "Cauã", "banner": arquivo})

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        self.assertTrue(perfil.banner.name.startswith("banners_perfil/"))
        with perfil.banner.open("rb") as arquivo_salvo:
            imagem = Image.open(arquivo_salvo)
            self.assertEqual(imagem.size, (1500, 844))
            self.assertEqual(imagem.format, "JPEG")

    def test_banner_estreito_e_mantido_inteiro(self):
        self.client.force_login(self.usuario)
        dados = BytesIO()
        Image.new("RGB", (800, 1200), color="green").save(dados, format="PNG")
        arquivo = SimpleUploadedFile("estreito.png", dados.getvalue(), content_type="image/png")

        response = self.client.post(reverse("profile:editar"), {"nome": "Cauã", "banner": arquivo})

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        with perfil.banner.open("rb") as arquivo_salvo:
            imagem = Image.open(arquivo_salvo)
            self.assertEqual(imagem.size, (800, 1200))
            self.assertEqual(imagem.format, "JPEG")

    def test_banner_pequeno_nao_aumenta_de_tamanho(self):
        self.client.force_login(self.usuario)
        dados = BytesIO()
        Image.new("RGB", (510, 180), color="red").save(dados, format="JPEG")
        arquivo = SimpleUploadedFile("banner_pequeno.jpg", dados.getvalue(), content_type="image/jpeg")

        response = self.client.post(reverse("profile:editar"), {"nome": "Cauã", "banner": arquivo})

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        with perfil.banner.open("rb") as arquivo_salvo:
            imagem = Image.open(arquivo_salvo)
            self.assertEqual(imagem.size, (510, 180))
            self.assertEqual(imagem.format, "JPEG")

    def test_banner_png_transparente_e_convertido_para_jpeg(self):
        self.client.force_login(self.usuario)
        dados = BytesIO()
        Image.new("RGBA", (1500, 500)).save(dados, format="PNG")
        arquivo = SimpleUploadedFile("transparente.png", dados.getvalue(), content_type="image/png")

        response = self.client.post(reverse("profile:editar"), {"nome": "Cauã", "banner": arquivo})

        self.assertRedirects(response, reverse("profile:perfil"))
        perfil = Perfil.objects.get(usuario=self.usuario)
        with perfil.banner.open("rb") as arquivo_salvo:
            imagem = Image.open(arquivo_salvo)
            self.assertEqual(imagem.size, (1500, 500))
            self.assertEqual(imagem.mode, "RGB")
            self.assertEqual(imagem.format, "JPEG")

    def test_perfil_publico_de_outro_usuario(self):
        outro = get_user_model().objects.get(username="outro")
        url = reverse("profile:perfil_publico", args=[outro.username])
        self.client.force_login(self.usuario)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "perfil_publico.html")
        self.assertContains(response, "@outro")
        self.assertContains(response, "Post de outra pessoa")
        self.assertContains(response, "Seguir")
        self.assertNotContains(response, "Editar perfil")

    def test_perfil_publico_do_proprio_usuario_redireciona(self):
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse("profile:perfil_publico", args=[self.usuario.username])
        )

        self.assertRedirects(response, reverse("profile:perfil"))

    def test_perfil_publico_exige_login(self):
        outro = get_user_model().objects.get(username="outro")

        response = self.client.get(reverse("profile:perfil_publico", args=[outro.username]))

        self.assertEqual(response.status_code, 302)

class DenunciarUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.denunciante = user_model.objects.create_user(
            username="denunciante",
            password="senha-teste",
        )
        cls.alvo = user_model.objects.create_user(
            username="alvo",
            password="senha-teste",
        )

    def test_perfil_publico_mostra_menu_de_denuncia(self):
        self.client.force_login(self.denunciante)

        resposta = self.client.get(
            reverse("profile:perfil_publico", args=[self.alvo.username])
        )

        self.assertContains(resposta, 'aria-label="Abrir opções do perfil"')
        self.assertContains(resposta, f"Denunciar @{self.alvo.username}")
        self.assertContains(resposta, 'id="report-profile-dialog"')
        self.assertContains(
            resposta,
            reverse("profile:denunciar_usuario", args=[self.alvo.username]),
        )

    def test_denuncia_cria_registro_e_impede_duplicada(self):
        self.client.force_login(self.denunciante)
        url = reverse("profile:denunciar_usuario", args=[self.alvo.username])
        retorno = reverse("profile:perfil_publico", args=[self.alvo.username])

        primeira = self.client.post(
            url,
            {
                "motivo": DenunciaUsuario.Motivo.FALSA_IDENTIDADE,
                "detalhes": "Perfil fingindo ser outra pessoa.",
                "return_path": retorno,
            },
        )
        segunda = self.client.post(
            url,
            {
                "motivo": DenunciaUsuario.Motivo.SPAM,
                "detalhes": "Segunda tentativa.",
                "return_path": retorno,
            },
        )

        self.assertRedirects(primeira, retorno)
        self.assertRedirects(segunda, retorno)
        self.assertEqual(DenunciaUsuario.objects.count(), 1)

        denuncia = DenunciaUsuario.objects.get()
        self.assertEqual(denuncia.denunciante, self.denunciante)
        self.assertEqual(denuncia.alvo, self.alvo)
        self.assertEqual(
            denuncia.motivo,
            DenunciaUsuario.Motivo.FALSA_IDENTIDADE,
        )
        self.assertEqual(
            denuncia.status,
            DenunciaUsuario.Status.PENDENTE,
        )

    def test_nao_pode_denunciar_o_proprio_perfil(self):
        self.client.force_login(self.denunciante)

        resposta = self.client.post(
            reverse(
                "profile:denunciar_usuario",
                args=[self.denunciante.username],
            ),
            {"motivo": DenunciaUsuario.Motivo.SPAM},
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(DenunciaUsuario.objects.exists())

    def test_motivo_invalido_nao_cria_denuncia(self):
        self.client.force_login(self.denunciante)
        retorno = reverse(
            "profile:perfil_publico",
            args=[self.alvo.username],
        )

        resposta = self.client.post(
            reverse(
                "profile:denunciar_usuario",
                args=[self.alvo.username],
            ),
            {
                "motivo": "nao-existe",
                "return_path": retorno,
            },
        )

        self.assertRedirects(resposta, retorno)
        self.assertFalse(DenunciaUsuario.objects.exists())

    def test_return_path_externo_e_ignorado(self):
        self.client.force_login(self.denunciante)

        resposta = self.client.post(
            reverse(
                "profile:denunciar_usuario",
                args=[self.alvo.username],
            ),
            {
                "motivo": DenunciaUsuario.Motivo.SPAM,
                "return_path": "https://evil.example/phishing",
            },
        )

        self.assertRedirects(
            resposta,
            reverse(
                "profile:perfil_publico",
                args=[self.alvo.username],
            ),
        )

class SelosDeContaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.visitante = user_model.objects.create_user(
            username="visitante-selos",
            password="senha-teste",
        )
        cls.verificado = user_model.objects.create_user(
            username="verificado",
            first_name="Verificado",
            password="senha-teste",
        )
        cls.staff = user_model.objects.create_user(
            username="equipe",
            first_name="Equipe",
            password="senha-teste",
            is_staff=True,
        )
        cls.normal = user_model.objects.create_user(
            username="normal",
            first_name="Normal",
            password="senha-teste",
        )
        Perfil.objects.create(usuario=cls.verificado, verificado=True)
        Perfil.objects.create(usuario=cls.staff)
        Perfil.objects.create(usuario=cls.normal)
        Post.objects.create(autor=cls.verificado, conteudo="Post verificado")
        Post.objects.create(autor=cls.staff, conteudo="Post da equipe")

    def test_perfil_novo_nao_e_verificado_por_padrao(self):
        perfil = Perfil.objects.create(
            usuario=get_user_model().objects.create_user(
                username="sem-selo",
                password="senha-teste",
            )
        )
        self.assertFalse(perfil.verificado)

    def test_perfil_publico_mostra_selo_verificado(self):
        self.client.force_login(self.visitante)

        resposta = self.client.get(
            reverse("profile:perfil_publico", args=[self.verificado.username])
        )

        self.assertContains(resposta, 'data-user-badge="verified"')
        self.assertContains(resposta, 'title="Conta verificada"')

    def test_staff_recebe_selo_automaticamente(self):
        self.client.force_login(self.visitante)

        resposta = self.client.get(
            reverse("profile:perfil_publico", args=[self.staff.username])
        )

        self.assertContains(resposta, 'data-user-badge="staff"')
        self.assertContains(resposta, "STAFF")
        self.assertContains(resposta, "Membro da equipe Krampt")

    def test_feed_mostra_os_dois_tipos_de_selo(self):
        self.client.force_login(self.visitante)

        resposta = self.client.get(reverse("home"))

        self.assertContains(resposta, "Post verificado")
        self.assertContains(resposta, "Post da equipe")
        self.assertContains(resposta, 'data-user-badge="verified"')
        self.assertContains(resposta, 'data-user-badge="staff"')

    def test_edicao_normal_de_perfil_nao_expoe_verificado(self):
        from .forms import EditarPerfilForm

        self.assertNotIn("verificado", EditarPerfilForm().fields)
