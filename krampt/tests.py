import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from posts.models import Post
from django.contrib.sessions.models import Session
from profile.models import Perfil


class StorageSettingsTests(SimpleTestCase):
    settings_path = Path(__file__).with_name("settings.py")

    def carregar_settings(self, variaveis=None):
        ambiente = {"SECRET_KEY": "chave-de-teste", **(variaveis or {})}
        with patch.dict(os.environ, ambiente, clear=True):
            return runpy.run_path(str(self.settings_path))

    def test_storage_local_e_fallback_sem_configuracao_completa_do_r2(self):
        configuracao = self.carregar_settings({"AWS_ACCESS_KEY_ID": "incompleta"})

        self.assertFalse(configuracao["R2_ENABLED"])
        self.assertEqual(
            configuracao["STORAGES"]["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )
        self.assertEqual(configuracao["MEDIA_ROOT"], configuracao["BASE_DIR"] / "media")

    def test_r2_configura_s3_e_whitenoise_sem_media_root(self):
        configuracao = self.carregar_settings({
            "AWS_ACCESS_KEY_ID": "access-key",
            "AWS_SECRET_ACCESS_KEY": "secret-key",
            "AWS_STORAGE_BUCKET_NAME": "krampt-media",
            "AWS_S3_ENDPOINT_URL": "https://conta.r2.cloudflarestorage.com",
            "AWS_S3_CUSTOM_DOMAIN": "media.krampt.test",
            "WHITENOISE": "true",
        })

        self.assertTrue(configuracao["R2_ENABLED"])
        self.assertEqual(configuracao["STORAGES"]["default"]["BACKEND"], "storages.backends.s3.S3Storage")
        self.assertEqual(
            configuracao["STORAGES"]["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertEqual(configuracao["AWS_S3_REGION_NAME"], "auto")
        self.assertFalse(configuracao["AWS_S3_FILE_OVERWRITE"])
        self.assertIsNone(configuracao["AWS_DEFAULT_ACL"])
        self.assertFalse(configuracao["AWS_QUERYSTRING_AUTH"])
        self.assertEqual(configuracao["AWS_S3_CUSTOM_DOMAIN"], "media.krampt.test")
        self.assertNotIn("MEDIA_ROOT", configuracao)


class AutenticacaoTests(TestCase):
    def test_paginas_exigem_login(self):
        usuario = get_user_model().objects.create_user(username="autor-do-post")
        post = Post.objects.create(autor=usuario, conteudo="Teste")
        for url in ["/buscar/", "/perfil/", "/mensagens/", "/notificacoes/", reverse("posts:detalhe", args=[post.pk]), reverse("posts:editar", args=[post.pk])]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"/login/?next={url}")

    def test_rota_antiga_de_posts_nao_existe(self):
        self.assertEqual(self.client.get("/post/").status_code, 404)

    def test_login_e_cadastro_continuam_publicos(self):
        for url in ["/login/", "/cadastro/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_atualizacao_revalida_sessao_e_pagina_nao_fica_em_cache(self):
        usuario = get_user_model().objects.create_user(username="sessao", password="senha")
        self.client.force_login(usuario)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        Session.objects.filter(session_key=self.client.session.session_key).delete()

        pagina_publica = self.client.get("/")
        self.assertEqual(pagina_publica.status_code, 200)
        self.assertContains(pagina_publica, "Uma rede feita para conversar")
        self.assertNotIn("_auth_user_id", self.client.session)

        self.assertRedirects(
            self.client.get("/buscar/"),
            "/login/?next=/buscar/",
        )


class LogoutTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="sair", password="Nuvem!Laranja927"
        )
        self.url = reverse("logout")

    def test_logout_por_post_desloga_e_redireciona(self):
        self.client.force_login(self.usuario)
        self.assertTrue(self.client.session.get("_auth_user_id"))

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("login:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.get(reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_por_get_retorna_405_e_nao_desloga(self):
        self.client.force_login(self.usuario)
        chave = self.client.session.session_key

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(Session.objects.filter(session_key=chave).exists())

    def test_logout_anonimo_vai_para_login(self):
        response = self.client.post(self.url)

        self.assertRedirects(response, "/login/?next=/logout/")

    def test_logout_sem_csrf_retorna_403(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)

        response = cliente.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertIn("_auth_user_id", cliente.session)

    def test_logout_realmente_invalida_a_sessao(self):
        self.client.force_login(self.usuario)
        chave = self.client.session.session_key
        self.client.post(self.url)

        self.assertFalse(Session.objects.filter(session_key=chave).exists())
        self.client.get(reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class BuscarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.caua = user_model.objects.create_user(
            username="caua", first_name="Cauã", password="senha-teste"
        )
        cls.maria = user_model.objects.create_user(
            username="maria_silva", first_name="Maria", password="senha-teste"
        )
        cls.post_da_maria = Post.objects.create(
            autor=cls.maria, conteudo="Aprendendo Django e buscando amigos"
        )

    def test_buscar_acha_pessoas_por_nome_e_username(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("buscar"), {"q": "maria"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "buscar.html")
        self.assertContains(response, "@maria_silva")

    def test_buscar_nao_lista_o_proprio_usuario_logado(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("buscar"), {"q": "cau"})

        self.assertNotContains(response, "@caua")

    def test_buscar_acha_posts_pelo_conteudo(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("buscar"), {"q": "django"})

        self.assertContains(response, "Aprendendo Django e buscando amigos")

    def test_buscar_sem_resultados_mostra_aviso(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("buscar"), {"q": "zzz-inexistente"})

        self.assertContains(response, "Nenhuma pessoa encontrada")
        self.assertContains(response, "Nenhum post encontrado")

    def test_buscar_sem_termo_mostra_passo_a_passo(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("buscar"))

        self.assertContains(response, "Digite um nome, @usuario ou palavra-chave")

    def test_buscar_exige_login(self):
        response = self.client.get(reverse("buscar"))

        self.assertEqual(response.status_code, 302)


class PaginacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="ana", password="senha")
        cls.outro = get_user_model().objects.create_user(username="caua", password="senha")
        for i in range(25):
            Post.objects.create(autor=cls.outro, conteudo=f"Noticia {i:02d}")
        perfil, _ = Perfil.objects.get_or_create(usuario=cls.usuario)
        perfil.seguindo.add(cls.outro)

    def test_feed_pagina_em_vinte_posts(self):
        self.client.force_login(self.usuario)

        pagina_um = self.client.get(reverse("home"))

        self.assertEqual(pagina_um.status_code, 200)
        self.assertEqual(len(pagina_um.context["posts"]), 20)
        self.assertTrue(pagina_um.context["pagina_objeto"].has_next())

        pagina_dois = self.client.get(reverse("home"), {"page": 2})

        self.assertEqual(len(pagina_dois.context["posts"]), 5)
        self.assertEqual(pagina_dois.context["pagina_objeto"].number, 2)
        self.assertFalse(pagina_dois.context["pagina_objeto"].has_next())

    def test_pagina_nao_existente_cai_na_ultima(self):
        self.client.force_login(self.usuario)

        pagina = self.client.get(reverse("home"), {"page": 999})

        self.assertEqual(pagina.context["pagina_objeto"].number, 2)

    def test_pagina_invalida_cai_na_primeira(self):
        self.client.force_login(self.usuario)

        pagina = self.client.get(reverse("home"), {"page": "abc"})

        self.assertEqual(pagina.context["pagina_objeto"].number, 1)

    def test_filtro_seguindo_e_mantido_ao_paginar(self):
        self.client.force_login(self.usuario)

        pagina = self.client.get(reverse("home"), {"filtro": "seguindo", "page": 2})

        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.context["parametros_url"], "filtro=seguindo")
        self.assertContains(pagina, "?filtro=seguindo&amp;page=1")
        self.assertEqual(len(pagina.context["posts"]), 5)

    def test_termo_de_busca_e_mantido_ao_paginar(self):
        self.client.force_login(self.usuario)

        pagina = self.client.get(reverse("buscar"), {"q": "Noticia", "page": 2})

        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "?q=Noticia&amp;page=1")
        self.assertEqual(len(pagina.context["posts"]), 5)
