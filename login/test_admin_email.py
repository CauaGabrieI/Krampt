from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse


User = get_user_model()


@override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}})
class TestarEmailAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="admin", password="senha", is_staff=True)
        cls.comum = User.objects.create_user(username="comum", password="senha")

    def test_visitante_vai_para_login(self):
        resposta = self.client.get(reverse("testar_email"))
        self.assertRedirects(resposta, "/login/?next=/admin/testar-email/")

    def test_usuario_comum_nao_acessa_nem_envia(self):
        self.client.force_login(self.comum)
        url = reverse("testar_email")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"email": "destino@example.com"}).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotContains(self.client.get(reverse("home")), "Testar e-mail")

    def test_admin_envia_para_email_informado(self):
        self.client.force_login(self.admin)
        url = reverse("testar_email")
        pagina = self.client.get(url)
        self.assertContains(pagina, 'name="email"')
        self.assertContains(pagina, "Testar e-mail")
        self.assertContains(self.client.get(reverse("home")), url)

        resposta = self.client.post(url, {"email": "destino@example.com"})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "servidor de e-mail aceitou")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["destino@example.com"])
        self.assertEqual(mail.outbox[0].subject, "Teste de e-mail do Krampt")

    def test_email_invalido_nao_envia(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("testar_email"), {"email": "invalido"})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["formulario"].errors)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}})
    def test_modo_console_avisa_que_nao_entrega_na_caixa_postal(self):
        self.client.force_login(self.admin)
        with patch("login.admin_views.send_mail", return_value=1):
            resposta = self.client.post(reverse("testar_email"), {"email": "destino@example.com"})
        self.assertContains(resposta, "Nenhum e-mail chegou à caixa de entrada")

    def test_falha_de_envio_e_mostrada_sem_detalhes_do_servidor(self):
        self.client.force_login(self.admin)
        with patch("login.admin_views.send_mail", side_effect=OSError("senha SMTP secreta")):
            resposta = self.client.post(reverse("testar_email"), {"email": "destino@example.com"})
        self.assertContains(resposta, "O envio falhou")
        self.assertNotContains(resposta, "senha SMTP secreta")

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        resposta = cliente.post(reverse("testar_email"), {"email": "destino@example.com"})
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
