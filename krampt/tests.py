from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from posts.models import Post
from django.contrib.sessions.models import Session


class AutenticacaoTests(TestCase):
    def test_paginas_exigem_login(self):
        usuario = get_user_model().objects.create_user(username="autor-do-post")
        post = Post.objects.create(autor=usuario, conteudo="Teste")
        for url in ["/", "/buscar/", "/perfil/", "/mensagens/", "/notificacoes/", reverse("posts:detalhe", args=[post.pk]), reverse("posts:editar", args=[post.pk])]:
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
        self.assertRedirects(self.client.get("/"), "/login/?next=/")


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
