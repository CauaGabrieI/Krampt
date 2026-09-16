from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from outbox.models import EventoOutbox
from profile.models import Perfil


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
        self.assertEqual(EventoOutbox.objects.count(), 0)
        self.assertNotContains(self.client.get(reverse("home")), "Testar e-mail")

    def test_admin_processa_teste_pela_outbox_em_modo_eager(self):
        self.client.force_login(self.admin)
        url = reverse("testar_email")
        pagina = self.client.get(url)
        self.assertContains(pagina, 'name="email"')
        self.assertContains(pagina, "Testar e-mail")
        self.assertContains(pagina, "Outbox")
        self.assertContains(self.client.get(reverse("home")), url)

        resposta = self.client.post(url, {"email": "destino@example.com"})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "fila da Outbox")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["destino@example.com"])
        self.assertEqual(mail.outbox[0].subject, "Teste de e-mail do Krampt")

        evento = EventoOutbox.objects.get(tipo="email.enviar")
        self.assertIsNotNone(evento.processado_em)
        self.assertEqual(evento.payload, {})

    @override_settings(OUTBOX_EAGER=False)
    def test_admin_enfileira_para_worker_sem_enviar_na_requisicao(self):
        self.client.force_login(self.admin)

        resposta = self.client.post(
            reverse("testar_email"),
            {"email": "destino@example.com"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "worker fará o envio")
        self.assertEqual(len(mail.outbox), 0)

        evento = EventoOutbox.objects.get(tipo="email.enviar")
        self.assertIsNone(evento.processado_em)
        self.assertIsNone(evento.descartado_em)
        self.assertEqual(evento.tentativas, 0)
        self.assertEqual(evento.payload["para"], ["destino@example.com"])
        self.assertEqual(evento.payload["assunto"], "Teste de e-mail do Krampt")
        self.assertIn("Transactional Outbox", evento.payload["texto"])

    def test_email_invalido_nao_enfileira(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("testar_email"), {"email": "invalido"})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["formulario"].errors)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EventoOutbox.objects.count(), 0)

    @override_settings(
        MAILERS={"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}},
        OUTBOX_EAGER=False,
    )
    def test_modo_console_avisa_que_worker_registra_no_console(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(
            reverse("testar_email"),
            {"email": "destino@example.com"},
        )
        self.assertContains(resposta, "fila da Outbox")
        self.assertContains(resposta, "console")
        self.assertEqual(EventoOutbox.objects.filter(tipo="email.enviar").count(), 1)

    def test_falha_ao_enfileirar_e_mostrada_sem_detalhes_do_servidor(self):
        self.client.force_login(self.admin)
        with patch(
            "login.admin_views.enfileirar_email",
            side_effect=OSError("senha SMTP secreta"),
        ):
            resposta = self.client.post(
                reverse("testar_email"),
                {"email": "destino@example.com"},
            )
        self.assertContains(resposta, "Não foi possível colocar o teste na fila")
        self.assertNotContains(resposta, "senha SMTP secreta")

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        resposta = cliente.post(
            reverse("testar_email"),
            {"email": "destino@example.com"},
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EventoOutbox.objects.count(), 0)


class ApagarUsuariosAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="admin", password="senha", is_staff=True)
        cls.staff_sem_permissao = User.objects.create_user(
            username="moderador",
            password="senha",
            is_staff=True,
        )
        cls.comum = User.objects.create_user(username="comum", password="senha")
        cls.alvo = User.objects.create_user(username="alvo", email="alvo@example.com", password="senha")

        permissao = Permission.objects.get(
            content_type__app_label=User._meta.app_label,
            content_type__model=User._meta.model_name,
            codename=f"delete_{User._meta.model_name}",
        )
        cls.admin.user_permissions.add(permissao)

    def test_visitante_vai_para_login(self):
        resposta = self.client.get(reverse("admin_apagar_usuarios"))
        self.assertRedirects(resposta, "/login/?next=/admin/apagar-usuarios/")

    def test_usuario_comum_nao_acessa_nem_apaga(self):
        self.client.force_login(self.comum)
        url = reverse("admin_apagar_usuarios")

        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(
                url,
                {
                    "usuario_id": self.alvo.pk,
                    "confirmacao": "alvo",
                    "senha_admin": "senha",
                },
            ).status_code,
            403,
        )
        self.assertTrue(User.objects.filter(pk=self.alvo.pk).exists())
        self.assertNotContains(self.client.get(reverse("home")), "Apagar usuários")

    def test_staff_sem_permissao_nao_acessa_nem_apaga(self):
        self.client.force_login(self.staff_sem_permissao)
        url = reverse("admin_apagar_usuarios")

        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(
                url,
                {
                    "usuario_id": self.alvo.pk,
                    "confirmacao": "alvo",
                    "senha_admin": "senha",
                },
            ).status_code,
            403,
        )
        self.assertTrue(User.objects.filter(pk=self.alvo.pk).exists())
        self.assertNotContains(
            self.client.get(reverse("home")),
            "Apagar usuários",
        )

    def test_admin_apaga_usuario_com_confirmacao_e_senha(self):
        self.client.force_login(self.admin)
        url = reverse("admin_apagar_usuarios")

        pagina = self.client.get(url)
        self.assertContains(pagina, "Apagar usuários")
        self.assertContains(self.client.get(reverse("home")), url)
        resposta = self.client.post(
            url,
            {
                "usuario_id": self.alvo.pk,
                "confirmacao": "alvo",
                "senha_admin": "senha",
            },
        )

        self.assertRedirects(resposta, url)
        self.assertFalse(User.objects.filter(pk=self.alvo.pk).exists())

    def test_admin_nao_apaga_com_senha_ou_confirmacao_errada(self):
        self.client.force_login(self.admin)
        url = reverse("admin_apagar_usuarios")

        self.client.post(
            url,
            {
                "usuario_id": self.alvo.pk,
                "confirmacao": "alvo",
                "senha_admin": "errada",
            },
        )
        self.assertTrue(User.objects.filter(pk=self.alvo.pk).exists())
        self.client.post(
            url,
            {
                "usuario_id": self.alvo.pk,
                "confirmacao": "outro",
                "senha_admin": "senha",
            },
        )
        self.assertTrue(User.objects.filter(pk=self.alvo.pk).exists())

    def test_admin_nao_apaga_a_si_mesmo_por_essa_tela(self):
        self.client.force_login(self.admin)

        self.client.post(
            reverse("admin_apagar_usuarios"),
            {
                "usuario_id": self.admin.pk,
                "confirmacao": "admin",
                "senha_admin": "senha",
            },
        )

        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        resposta = cliente.post(
            reverse("admin_apagar_usuarios"),
            {
                "usuario_id": self.alvo.pk,
                "confirmacao": "alvo",
                "senha_admin": "senha",
            },
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.alvo.pk).exists())

class VerificarUsuariosAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin-verificacao",
            password="senha",
            is_staff=True,
        )
        cls.staff_sem_permissao = User.objects.create_user(
            username="moderador-verificacao",
            password="senha",
            is_staff=True,
        )
        cls.comum = User.objects.create_user(
            username="comum-verificacao",
            password="senha",
        )
        cls.alvo = User.objects.create_user(
            username="alvo-verificacao",
            first_name="Alvo",
            email="alvo-verificacao@example.com",
            password="senha",
        )
        Perfil.objects.create(usuario=cls.alvo)

        permissao = Permission.objects.get(
            content_type__app_label="profile",
            content_type__model="perfil",
            codename="change_perfil",
        )
        cls.admin.user_permissions.add(permissao)

    def test_visitante_vai_para_login(self):
        resposta = self.client.get(reverse("admin_verificar_usuarios"))

        self.assertRedirects(
            resposta,
            "/login/?next=/admin/verificar-usuarios/",
        )

    def test_staff_sem_permissao_nao_acessa(self):
        self.client.force_login(self.staff_sem_permissao)

        resposta = self.client.get(reverse("admin_verificar_usuarios"))

        self.assertEqual(resposta.status_code, 403)
        self.assertNotContains(
            self.client.get(reverse("home")),
            "Verificar usuários",
        )

    def test_usuario_comum_nao_acessa(self):
        self.client.force_login(self.comum)

        resposta = self.client.get(reverse("admin_verificar_usuarios"))

        self.assertEqual(resposta.status_code, 403)

    def test_admin_com_permissao_acessa_e_encontra_usuario(self):
        self.client.force_login(self.admin)
        url = reverse("admin_verificar_usuarios")

        resposta = self.client.get(url, {"q": "alvo-verificacao"})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "@alvo-verificacao")
        self.assertContains(resposta, "Conceder verificado")
        self.assertContains(self.client.get(reverse("home")), url)

    def test_admin_concede_e_remove_verificado(self):
        self.client.force_login(self.admin)
        url = reverse("admin_verificar_usuarios")

        resposta = self.client.post(
            url,
            {
                "usuario_id": self.alvo.pk,
                "desired_state": "1",
            },
        )
        self.assertRedirects(resposta, url)
        self.alvo.perfil.refresh_from_db()
        self.assertTrue(self.alvo.perfil.verificado)

        resposta = self.client.post(
            url,
            {
                "usuario_id": self.alvo.pk,
                "desired_state": "0",
            },
        )
        self.assertRedirects(resposta, url)
        self.alvo.perfil.refresh_from_db()
        self.assertFalse(self.alvo.perfil.verificado)

    def test_tela_cria_perfil_quando_usuario_ainda_nao_tem(self):
        sem_perfil = User.objects.create_user(
            username="sem-perfil-verificacao",
            password="senha",
        )
        self.client.force_login(self.admin)

        resposta = self.client.post(
            reverse("admin_verificar_usuarios"),
            {
                "usuario_id": sem_perfil.pk,
                "desired_state": "1",
            },
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(
            Perfil.objects.get(usuario=sem_perfil).verificado
        )

    def test_post_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)

        resposta = cliente.post(
            reverse("admin_verificar_usuarios"),
            {
                "usuario_id": self.alvo.pk,
                "desired_state": "1",
            },
        )

        self.assertEqual(resposta.status_code, 403)
        self.alvo.perfil.refresh_from_db()
        self.assertFalse(self.alvo.perfil.verificado)
