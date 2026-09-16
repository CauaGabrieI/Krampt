from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class PublicSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="public-site-user",
            password="Senha-forte-123!",
        )

    def test_home_e_publica_para_visitante(self):
        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Uma rede feita para conversar")
        self.assertContains(resposta, "Criar minha conta")
        self.assertContains(resposta, reverse("privacidade"))
        self.assertContains(resposta, reverse("diretrizes"))

    def test_home_continua_feed_para_usuario_logado(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "O que está acontecendo?")
        self.assertNotContains(resposta, "Uma rede feita para conversar")

    def test_paginas_institucionais_sao_publicas(self):
        casos = (
            ("sobre", "Sobre o Krampt"),
            ("privacidade", "Política de Privacidade"),
            ("termos", "Termos de Uso"),
            ("diretrizes", "Diretrizes da Comunidade"),
        )

        for nome, texto in casos:
            with self.subTest(nome=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, texto)

    def test_robots_txt_e_publico_e_nao_bloqueia_crawlers_de_ads(self):
        resposta = self.client.get(reverse("robots_txt"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.headers["Content-Type"],
            "text/plain; charset=utf-8",
        )
        corpo = resposta.content.decode()
        self.assertIn("User-agent: Mediapartners-Google", corpo)
        self.assertIn("User-agent: Google-Display-Ads-Bot", corpo)
        self.assertIn("Allow: /", corpo)
        self.assertIn("/sitemap.xml", corpo)

    def test_sitemap_xml_lista_paginas_publicas(self):
        resposta = self.client.get(reverse("sitemap_xml"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.headers["Content-Type"],
            "application/xml; charset=utf-8",
        )
        corpo = resposta.content.decode()
        for nome in (
            "home",
            "sobre",
            "diretrizes",
            "privacidade",
            "termos",
            "login:login",
            "cadastro",
        ):
            self.assertIn(reverse(nome), corpo)

    def test_login_e_cadastro_exibem_links_institucionais(self):
        for nome in ("login:login", "cadastro"):
            with self.subTest(nome=nome):
                resposta = self.client.get(reverse(nome))
                self.assertContains(resposta, reverse("privacidade"))
                self.assertContains(resposta, reverse("termos"))
                self.assertContains(resposta, reverse("diretrizes"))

    def test_post_anonimo_na_home_nao_cria_conteudo(self):
        resposta = self.client.post(reverse("home"), {"conteudo": "não deve criar"})

        self.assertRedirects(resposta, reverse("login:login"))
