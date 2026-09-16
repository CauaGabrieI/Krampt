from django.contrib.auth import get_user_model
from django.core import mail
from django.contrib.sessions.models import Session
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import os
import re
from unittest.mock import patch

from configuracoes.models import PreferenciasUsuario
from login.models import LimiteAutenticacao, VerificacaoEmail
from login.services import mascarar_email, obter_ip_cliente
from django.core import management
from io import StringIO

User = get_user_model()


class CadastroTests(TestCase):
    def dados(self, **alteracoes):
        dados = dict(name='  Ana   Maria  ', username=' an a\t ', email=' ANA@EXAMPLE.COM ', password='Nuvem!Laranja927', password_confirm='Nuvem!Laranja927', aceitou_termos='1')
        dados.update(alteracoes)
        return dados

    def test_normaliza_dados_e_salva_senha_com_hash(self):
        response = self.client.post(reverse('cadastro'), self.dados())
        self.assertRedirects(response, reverse('verificar_email'))
        usuario = User.objects.get()
        self.assertEqual(usuario.username, 'ana')
        self.assertEqual(usuario.first_name, 'Ana Maria')
        self.assertEqual(usuario.email, 'ana@example.com')
        self.assertNotEqual(usuario.password, 'Nuvem!Laranja927')
        self.assertTrue(usuario.check_password('Nuvem!Laranja927'))
        self.assertFalse(usuario.is_active)
        self.assertTrue(VerificacaoEmail.objects.filter(usuario=usuario, verificado_em__isnull=True).exists())

    def test_exige_aceite_dos_termos_no_backend(self):
        dados = self.dados()
        dados.pop('aceitou_termos')

        response = self.client.post(reverse('cadastro'), dados)

        self.assertEqual(response.status_code, 200)
        self.assertIn('aceitou_termos', response.context['formulario'].errors)
        self.assertContains(
            response,
            'Você precisa aceitar os Termos de Uso e a Política de Privacidade para criar a conta.',
        )
        self.assertFalse(User.objects.exists())

    def test_cadastro_exibe_checkbox_e_links_dos_termos(self):
        response = self.client.get(reverse('cadastro'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="aceitou_termos"', html=False)
        self.assertContains(response, reverse('termos'))
        self.assertContains(response, reverse('privacidade'))
        self.assertContains(response, reverse('diretrizes'))

    def test_rejeita_campos_invalidos_no_backend(self):
        casos = [dict(password_confirm='OutraSenha'), dict(password_confirm=''), dict(email='invalido'), dict(email='ana @example.com'), dict(username='!!!'), dict(username='   '), dict(name=' \t '), dict(username='a' * 151), dict(email='a' * 255 + '@example.com')]
        for alteracoes in casos:
            with self.subTest(alteracoes=alteracoes):
                response = self.client.post(reverse('cadastro'), self.dados(**alteracoes))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['formulario'].errors)
                self.assertFalse(User.objects.exists())
                self.assertNotContains(response, 'Nuvem!Laranja927')

    def test_rejeita_senhas_fracas(self):
        for senha in ['Ab!29', '123456789012', 'password123', 'ana@example.com', 'nuvem!laranja927', 'NUVEM!LARANJA927', 'Nuvem!LaranjaXYZ', 'NuvemLaranja927']:
            with self.subTest(senha=senha):
                response = self.client.post(reverse('cadastro'), self.dados(password=senha, password_confirm=senha))
                self.assertIn('password', response.context['formulario'].errors)
                self.assertFalse(User.objects.exists())

    def test_nao_altera_espacos_da_senha(self):
        senha = ' Nuvem!Laranja927 '
        self.client.post(reverse('cadastro'), self.dados(password=senha, password_confirm=senha))
        usuario = User.objects.get()
        self.assertTrue(usuario.check_password(senha))
        self.assertFalse(usuario.check_password(senha.strip()))

    def test_rejeita_duplicados_independente_de_caixa(self):
        User.objects.create_user(username='Ana', email='ANA@example.com', password='senha')
        for dados in [self.dados(email='outro@example.com'), self.dados(username='outra')]:
            response = self.client.post(reverse('cadastro'), dados)
            self.assertTrue(response.context['formulario'].errors)
            self.assertEqual(User.objects.count(), 1)

    def test_csrf_exigido(self):
        response = Client(enforce_csrf_checks=True).post(reverse('cadastro'), self.dados())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_cadastro_com_csrf_da_sessao_sem_cookie_extra(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse('cadastro'))
        self.assertNotIn('csrftoken', response.cookies)
        dados = self.dados()
        dados['csrfmiddlewaretoken'] = str(response.context['csrf_token'])
        response = client.post(reverse('cadastro'), dados)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='ana').exists())


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username='ana', password='Nuvem!Laranja927')

    def test_login_normaliza_usuario_e_rotaciona_sessao(self):
        self.client.get(reverse('login:login'))
        chave_antiga = self.client.session.session_key
        response = self.client.post(reverse('login:login') + '?next=/mensagens/', {'username': ' a na ', 'password': 'Nuvem!Laranja927'})
        self.assertRedirects(response, '/mensagens/')
        self.assertNotEqual(self.client.session.session_key, chave_antiga)
        self.assertFalse(Session.objects.filter(session_key=chave_antiga).exists())
        cookie = response.cookies['sessionid']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertFalse(cookie['expires'])
        self.assertNotIn('csrftoken', response.cookies)
        self.assertNotIn('password', self.client.session)

    def test_login_nao_redireciona_para_site_externo(self):
        response = self.client.post(reverse('login:login') + '?next=https://example.org/', {'username': 'ana', 'password': 'Nuvem!Laranja927'})
        self.assertRedirects(response, reverse('home'))

    def test_erro_generico_e_sem_reexibir_senha(self):
        for username in ['ana', 'naoexiste']:
            response = self.client.post(reverse('login:login'), {'username': username, 'password': 'SenhaErrada!927'})
            self.assertContains(response, 'Usuário ou senha inválidos.')
            self.assertNotContains(response, 'SenhaErrada!927')
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_usuario_inativo_nao_entra(self):
        self.usuario.is_active = False
        self.usuario.save()
        response = self.client.post(reverse('login:login'), {'username': 'ana', 'password': 'Nuvem!Laranja927'})
        self.assertContains(response, 'Usuário ou senha inválidos.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_por_email_funciona_para_conta_ativa(self):
        self.usuario.email = "ana@example.com"
        self.usuario.save(update_fields=["email"])
        response = self.client.post(
            reverse("login:login"),
            {"username": " ANA@example.com ", "password": "Nuvem!Laranja927"},
        )
        self.assertRedirects(response, reverse("home"))

    def test_login_conta_desativada_senha_errada_nao_oferece_reativacao(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=self.usuario)
        preferencias.desativada_em = timezone.now()
        preferencias.save(update_fields=["desativada_em"])

        response = self.client.post(
            reverse("login:login"),
            {"username": "ana", "password": "errada"},
        )

        self.assertContains(response, "Usuário ou senha inválidos.")
        self.assertNotIn("reativacao_usuario_id", self.client.session)
        self.assertEqual(len(mail.outbox), 0)

    def test_login_conta_desativada_senha_correta_abre_tela_sem_enviar_email(self):
        self.usuario.email = "ana@example.com"
        self.usuario.is_active = False
        self.usuario.save(update_fields=["email", "is_active"])
        preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=self.usuario)
        preferencias.desativada_em = timezone.now()
        preferencias.save(update_fields=["desativada_em"])

        response = self.client.post(
            reverse("login:login"),
            {"username": "ana@example.com", "password": "Nuvem!Laranja927"},
        )

        self.assertRedirects(response, reverse("reativar_conta"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.session["reativacao_usuario_id"], self.usuario.pk)
        self.assertEqual(len(mail.outbox), 0)

    def test_login_inativo_por_verificacao_nao_cai_em_reativacao(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        VerificacaoEmail.objects.create(usuario=self.usuario)

        response = self.client.post(
            reverse("login:login"),
            {"username": "ana", "password": "Nuvem!Laranja927"},
        )

        self.assertRedirects(response, reverse("verificar_email"))
        self.assertNotIn("reativacao_usuario_id", self.client.session)

    def test_bloqueia_login_apos_tentativas_excessivas(self):
        for _ in range(5):
            self.client.post(reverse('login:login'), {'username': 'ana', 'password': 'errada'})
        response = self.client.post(reverse('login:login'), {'username': 'ana', 'password': 'Nuvem!Laranja927'})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Tentativas excessivas', status_code=429)
        self.assertNotIn('_auth_user_id', self.client.session)


@override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}})
class ReativacaoContaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="ana",
            email="ana@example.com",
            password="Nuvem!Laranja927",
            is_active=False,
        )
        self.preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=self.usuario)
        self.preferencias.desativada_em = timezone.now()
        self.preferencias.save(update_fields=["desativada_em"])
        sessao = self.client.session
        sessao["reativacao_usuario_id"] = self.usuario.pk
        sessao.save()

    def _token_email(self):
        match = re.search(r"/conta/reativar/([^/\s]+)/", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_tela_exige_tentativa_valida_e_mascara_email(self):
        outro = Client()
        self.assertRedirects(outro.get(reverse("reativar_conta")), reverse("login:login"))

        resposta = self.client.get(reverse("reativar_conta"))

        self.assertContains(resposta, "a***@example.com")
        self.assertNotContains(resposta, "ana@example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_post_envia_link_e_armazena_apenas_hash(self):
        resposta = self.client.post(reverse("reativar_conta"))

        self.assertContains(resposta, "Enviamos um link de reativação")
        self.assertEqual(len(mail.outbox), 1)
        token = self._token_email()
        self.preferencias.refresh_from_db()
        self.assertNotEqual(self.preferencias.token_reativacao_hash, "")
        self.assertNotIn(token, self.preferencias.token_reativacao_hash)
        self.assertIsNotNone(self.preferencias.token_reativacao_expira_em)

    def test_post_de_reativacao_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        sessao = cliente.session
        sessao["reativacao_usuario_id"] = self.usuario.pk
        sessao.save()

        resposta = cliente.post(reverse("reativar_conta"))

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit_de_envio(self):
        self.client.post(reverse("reativar_conta"))
        resposta = self.client.post(reverse("reativar_conta"))

        self.assertContains(resposta, "Um link já foi solicitado recentemente.")
        self.assertEqual(len(mail.outbox), 1)

    def test_limite_por_janela_permite_somente_tres_envios(self):
        for _ in range(3):
            resposta = self.client.post(reverse("reativar_conta"))
            self.assertEqual(resposta.status_code, 200)
            self.preferencias.refresh_from_db()
            self.preferencias.reativacao_ultimo_envio_em = timezone.now() - timedelta(minutes=6)
            self.preferencias.save(update_fields=["reativacao_ultimo_envio_em"])

        resposta = self.client.post(reverse("reativar_conta"))

        self.assertEqual(resposta.status_code, 429)
        self.assertContains(
            resposta,
            "Um link já foi solicitado recentemente.",
            status_code=429,
        )
        self.assertEqual(len(mail.outbox), 3)

    def test_conta_ativa_nao_acessa_fluxo_de_reativacao(self):
        self.usuario.is_active = True
        self.usuario.save(update_fields=["is_active"])

        resposta = self.client.get(reverse("reativar_conta"))

        self.assertRedirects(resposta, reverse("login:login"))
        self.assertNotIn("reativacao_usuario_id", self.client.session)
        self.assertEqual(len(mail.outbox), 0)

    def test_token_valido_reativa_e_invalida_o_link(self):
        self.client.post(reverse("reativar_conta"))
        token = self._token_email()

        resposta = self.client.get(reverse("reativar_conta_token", args=[token]))

        self.assertRedirects(resposta, reverse("login:login"))
        self.usuario.refresh_from_db()
        self.preferencias.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        self.assertIsNone(self.preferencias.desativada_em)
        self.assertEqual(self.preferencias.token_reativacao_hash, "")
        self.assertIsNone(self.preferencias.token_reativacao_expira_em)
        self.assertRedirects(
            self.client.post(
                reverse("login:login"),
                {"username": "ana", "password": "Nuvem!Laranja927"},
            ),
            reverse("home"),
        )
        self.client.logout()
        self.assertContains(
            self.client.get(reverse("reativar_conta_token", args=[token])),
            "inválido ou expirou",
            status_code=400,
        )

    def test_token_expirado_ou_invalido_falha(self):
        self.client.post(reverse("reativar_conta"))
        token = self._token_email()
        self.preferencias.refresh_from_db()
        self.preferencias.token_reativacao_expira_em = timezone.now() - timedelta(seconds=1)
        self.preferencias.save(update_fields=["token_reativacao_expira_em"])

        self.assertContains(
            self.client.get(reverse("reativar_conta_token", args=[token])),
            "inválido ou expirou",
            status_code=400,
        )
        self.assertContains(
            self.client.get(reverse("reativar_conta_token", args=["token-inventado"])),
            "inválido ou expirou",
            status_code=400,
        )
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)

    def test_novo_token_invalida_o_anterior(self):
        self.client.post(reverse("reativar_conta"))
        antigo = self._token_email()
        self.preferencias.refresh_from_db()
        self.preferencias.reativacao_ultimo_envio_em = timezone.now() - timedelta(minutes=6)
        self.preferencias.save(update_fields=["reativacao_ultimo_envio_em"])

        self.client.post(reverse("reativar_conta"))
        novo = self._token_email()

        self.assertContains(
            self.client.get(reverse("reativar_conta_token", args=[antigo])),
            "inválido ou expirou",
            status_code=400,
        )
        self.assertRedirects(
            self.client.get(reverse("reativar_conta_token", args=[novo])),
            reverse("login:login"),
        )


@override_settings(MAILERS={
    'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}
})
class VerificacaoEmailTests(TestCase):
    def cadastrar(self, client=None, username='ana', email='ana@example.com'):
        client = client or self.client
        response = client.post(reverse('cadastro'), {
            'name': 'Ana Maria', 'username': username, 'email': email,
            'password': 'Nuvem!Laranja927', 'password_confirm': 'Nuvem!Laranja927',
            'aceitou_termos': '1',
        })
        self.assertRedirects(response, reverse('verificar_email'))
        return User.objects.get(username=username)

    def codigo_email(self, indice=-1):
        return re.search(r'código é (\d{6})', mail.outbox[indice].body).group(1)

    def test_cadastro_envia_codigo_e_login_so_funciona_apos_confirmar(self):
        usuario = self.cadastrar()
        codigo = self.codigo_email()
        verificacao = VerificacaoEmail.objects.get(usuario=usuario)
        self.assertNotIn(codigo, verificacao.codigo_hash)
        self.assertFalse(usuario.is_active)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('login:login'), {'username': 'ana', 'password': 'Nuvem!Laranja927'})
        self.assertRedirects(response, reverse('verificar_email'))
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('verificar_email'), {'codigo': codigo})
        self.assertRedirects(response, reverse('login:login'))
        usuario.refresh_from_db()
        verificacao.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertIsNotNone(verificacao.verificado_em)
        self.assertEqual(verificacao.codigo_hash, '')
        self.assertIsNone(verificacao.expira_em)
        self.assertNotIn('verificacao_usuario_id', self.client.session)
        self.assertRedirects(self.client.post(reverse('verificar_email'), {'codigo': codigo}), reverse('cadastro'))
        self.assertRedirects(self.client.post(reverse('login:login'), {'username': 'ana', 'password': 'Nuvem!Laranja927'}), reverse('home'))

    def test_codigo_errado_expirado_e_de_outro_usuario(self):
        usuario = self.cadastrar()
        codigo = self.codigo_email()
        self.assertContains(self.client.post(reverse('verificar_email'), {'codigo': '999999' if codigo != '999999' else '999998'}), 'Código inválido')
        outra = Client()
        outro = self.cadastrar(outra, username='bia', email='bia@example.com')
        self.assertContains(outra.post(reverse('verificar_email'), {'codigo': codigo}), 'Código inválido')
        self.assertFalse(outro.is_active)
        verificacao = VerificacaoEmail.objects.get(usuario=usuario)
        verificacao.expira_em = timezone.now() - timedelta(seconds=1)
        verificacao.save(update_fields=['expira_em'])
        self.assertContains(self.client.post(reverse('verificar_email'), {'codigo': codigo}), 'Código expirado')
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_reenvio_invalida_codigo_anterior_e_tem_limite(self):
        usuario = self.cadastrar()
        antigo = self.codigo_email()
        verificacao = VerificacaoEmail.objects.get(usuario=usuario)
        self.assertContains(self.client.post(reverse('verificar_email'), {'acao': 'reenviar'}), 'Aguarde 60 segundos')
        self.assertEqual(len(mail.outbox), 1)
        for _ in range(3):
            verificacao.ultimo_envio_em = timezone.now() - timedelta(seconds=61)
            verificacao.save(update_fields=['ultimo_envio_em'])
            self.assertContains(self.client.post(reverse('verificar_email'), {'acao': 'reenviar'}), 'Novo código enviado')
            verificacao.refresh_from_db()
        self.assertEqual(len(mail.outbox), 4)
        self.assertNotEqual(self.codigo_email(), antigo)
        verificacao.ultimo_envio_em = timezone.now() - timedelta(seconds=61)
        verificacao.save(update_fields=['ultimo_envio_em'])
        self.assertContains(self.client.post(reverse('verificar_email'), {'acao': 'reenviar'}), 'Limite de reenvios', status_code=429)
        self.assertContains(self.client.post(reverse('verificar_email'), {'codigo': antigo}), 'Código inválido')

    def test_troca_email_pendente_envia_novo_codigo_e_invalida_antigo(self):
        usuario = self.cadastrar()
        antigo = self.codigo_email()

        resposta = self.client.post(
            reverse("verificar_email"),
            {"acao": "trocar_email", "email": "novo@example.com"},
        )

        self.assertContains(resposta, "E-mail alterado. Enviamos um novo código.")
        usuario.refresh_from_db()
        self.assertEqual(usuario.email, "novo@example.com")
        self.assertEqual(mail.outbox[-1].to, ["novo@example.com"])
        self.assertContains(self.client.post(reverse("verificar_email"), {"codigo": antigo}), "Código inválido")

    def test_troca_email_pendente_rejeita_email_em_uso(self):
        User.objects.create_user(username="bia", email="bia@example.com", password="Nuvem!Laranja927")
        usuario = self.cadastrar()

        resposta = self.client.post(
            reverse("verificar_email"),
            {"acao": "trocar_email", "email": "BIA@example.com"},
        )

        self.assertContains(resposta, "Este e-mail já está em uso.")
        usuario.refresh_from_db()
        self.assertEqual(usuario.email, "ana@example.com")

    def test_codigo_bloqueado_apos_cinco_erros(self):
        usuario = self.cadastrar()
        codigo = self.codigo_email()
        errado = '999999' if codigo != '999999' else '999998'
        for _ in range(4):
            self.assertContains(self.client.post(reverse('verificar_email'), {'codigo': errado}), 'Código inválido')
        self.assertContains(self.client.post(reverse('verificar_email'), {'codigo': errado}), 'Tentativas excessivas', status_code=429)
        self.assertEqual(self.client.post(reverse('verificar_email'), {'codigo': codigo}).status_code, 429)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_link_de_verificacao_precisa_da_sessao(self):
        self.cadastrar()
        outro_navegador = Client()
        self.assertRedirects(outro_navegador.get(reverse('verificar_email')), reverse('cadastro'))

    def test_falha_no_email_nao_deixa_conta_inativa_presa(self):
        with patch('login.services._enviar_email', side_effect=OSError('SMTP indisponível')):
            response = self.client.post(reverse('cadastro'), {
                'name': 'Ana Maria', 'username': 'ana', 'email': 'ana@example.com',
                'password': 'Nuvem!Laranja927', 'password_confirm': 'Nuvem!Laranja927',
                'aceitou_termos': '1',
            })
        self.assertContains(response, 'Não foi possível enviar o código')
        self.assertFalse(User.objects.exists())
        self.assertFalse(VerificacaoEmail.objects.exists())

    def test_verificacao_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse('cadastro'))
        dados = {
            'name': 'Ana Maria', 'username': 'ana', 'email': 'ana@example.com',
            'password': 'Nuvem!Laranja927', 'password_confirm': 'Nuvem!Laranja927',
            'aceitou_termos': '1',
            'csrfmiddlewaretoken': str(response.context['csrf_token']),
        }
        client.post(reverse('cadastro'), dados)
        codigo = self.codigo_email()
        self.assertEqual(client.post(reverse('verificar_email'), {'codigo': codigo}).status_code, 403)
        self.assertFalse(User.objects.get(username='ana').is_active)


class MascararEmailTests(TestCase):
    def test_mascara_local_do_email(self):
        self.assertEqual(mascarar_email("ana@example.com"), "a***@example.com")
        self.assertEqual(mascarar_email("carlos@dominio.org.br"), "c***@dominio.org.br")

    def test_email_sem_arroba_retorna_original(self):
        self.assertEqual(mascarar_email("invalido"), "invalido")
        self.assertIsNone(mascarar_email(None))


class VerificacaoEmailMascaradoTests(TestCase):
    def test_pagina_mostra_email_mascarado(self):
        self.client.post(reverse("cadastro"), {
            "name": "Ana Maria", "username": "ana", "email": "ana@example.com",
            "password": "Nuvem!Laranja927", "password_confirm": "Nuvem!Laranja927",
            'aceitou_termos': '1',
        })
        resposta = self.client.get(reverse("verificar_email"))
        self.assertContains(resposta, "a***@example.com")
        self.assertNotContains(resposta, "ana@example.com")


class LimparAutenticacaoExpiradaTests(TestCase):
    def _criar_contas(self):
        antiga = User.objects.create_user(username="antiga", password="senha")
        antiga.date_joined = timezone.now() - timedelta(days=5)
        antiga.is_active = False
        antiga.save()
        VerificacaoEmail.objects.create(usuario=antiga, codigo_hash="x" * 64, expira_em=timezone.now() - timedelta(hours=2))
        recente = User.objects.create_user(username="recente", password="senha")
        recente.date_joined = timezone.now() - timedelta(hours=2)
        recente.is_active = False
        recente.save()
        VerificacaoEmail.objects.create(usuario=recente)
        verificada = User.objects.create_user(username="verificada", password="senha")
        verificada.date_joined = timezone.now() - timedelta(days=5)
        verificada.save()
        VerificacaoEmail.objects.create(usuario=verificada, verificado_em=timezone.now())
        return antiga, recente, verificada

    def _criar_limites(self):
        LimiteAutenticacao.objects.create(chave="antigo", tentativas=1, janela_iniciada_em=timezone.now() - timedelta(days=5))
        LimiteAutenticacao.objects.create(chave="bloqueado_expirado", tentativas=5, janela_iniciada_em=timezone.now() - timedelta(days=5), bloqueado_ate=timezone.now() - timedelta(hours=1))
        LimiteAutenticacao.objects.create(chave="bloqueado_ativa", tentativas=5, janela_iniciada_em=timezone.now() - timedelta(days=5), bloqueado_ate=timezone.now() + timedelta(hours=1))
        LimiteAutenticacao.objects.create(chave="recente", tentativas=1, janela_iniciada_em=timezone.now() - timedelta(hours=2))

    def test_dry_run_nao_altera_nada(self):
        antiga, _, _ = self._criar_contas()
        self._criar_limites()
        self.assertEqual(management.call_command("limpar_autenticacao_expirada", "--dry-run", stdout=StringIO()), None)
        self.assertTrue(User.objects.filter(pk=antiga.pk).exists())
        self.assertEqual(LimiteAutenticacao.objects.count(), 4)

    def test_remove_apenas_o_expirado(self):
        antiga, recente, verificada = self._criar_contas()
        self._criar_limites()
        management.call_command("limpar_autenticacao_expirada", stdout=StringIO())
        self.assertFalse(User.objects.filter(pk=antiga.pk).exists())
        self.assertTrue(User.objects.filter(pk=recente.pk).exists())
        self.assertTrue(User.objects.filter(pk=verificada.pk).exists())
        self.assertEqual(LimiteAutenticacao.objects.filter(chave="antigo").count(), 0)
        self.assertEqual(LimiteAutenticacao.objects.filter(chave="bloqueado_expirado").count(), 0)
        self.assertEqual(LimiteAutenticacao.objects.filter(chave="bloqueado_ativa").count(), 1)
        self.assertEqual(LimiteAutenticacao.objects.filter(chave="recente").count(), 1)

    def test_prazo_personalizado(self):
        antiga, recente, _ = self._criar_contas()
        management.call_command("limpar_autenticacao_expirada", "--prazo-horas", 1, stdout=StringIO())
        self.assertFalse(User.objects.filter(pk=antiga.pk).exists())
        self.assertFalse(User.objects.filter(pk=recente.pk).exists())


@override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}})
class RedefinirSenhaTests(TestCase):
    def _url_recuperacao(self):
        corpo = mail.outbox[-1].body
        return re.search(r"http://testserver(/login/senha/[^\s]+)", corpo).group(1)

    def test_pagina_de_recuperacao_e_acessivel_sem_login(self):
        resposta = self.client.get(reverse("login:password_reset"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Esqueci minha senha")

    def test_resposta_generica_e_so_envia_para_conta_existente(self):
        usuario = User.objects.create_user(username="ana", password="Nuvem!Laranja927", email="ana@example.com")
        resposta = self.client.post(reverse("login:password_reset"), {"email": "ana@example.com"})
        self.assertRedirects(resposta, reverse("login:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@example.com"])
        resposta = self.client.post(reverse("login:password_reset"), {"email": "nao-existe@example.com"})
        self.assertRedirects(resposta, reverse("login:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_nao_envia_para_conta_inativa_ou_desativada(self):
        User.objects.create_user(username="inativa", password="senha", email="inativa@example.com", is_active=False)
        self.client.post(reverse("login:password_reset"), {"email": "inativa@example.com"})
        self.assertEqual(len(mail.outbox), 0)

    def test_fluxo_completo_de_redefinicao_de_senha(self):
        usuario = User.objects.create_user(username="ana", password="Nuvem!Laranja927", email="ana@example.com")
        self.client.post(reverse("login:password_reset"), {"email": "ana@example.com"})
        url = self._url_recuperacao()
        pagina = self.client.get(url, follow=True)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Crie uma nova senha")
        url_formulario = pagina.redirect_chain[-1][0]
        resposta = self.client.post(url_formulario, {
            "new_password1": "Outra!Senha2810",
            "new_password2": "Outra!Senha2810",
        })
        self.assertRedirects(resposta, reverse("login:password_reset_complete"))
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("Outra!Senha2810"))
        self.assertFalse(usuario.check_password("Nuvem!Laranja927"))
        self.assertRedirects(self.client.post(reverse("login:login"), {"username": "ana", "password": "Outra!Senha2810"}), reverse("home"))

    def test_link_invalido_nao_redefine_senha(self):
        usuario = User.objects.create_user(username="ana", password="Nuvem!Laranja927", email="ana@example.com")
        resposta = self.client.get(reverse("login:password_reset_confirm", kwargs={"uidb64": "abc", "token": "abcd-efgh"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "link de recuperação é inválido")
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("Nuvem!Laranja927"))

    def test_rate_limit_nas_solicitacoes(self):
        for _ in range(5):
            resposta = self.client.post(reverse("login:password_reset"), {"email": "nao-existe@example.com"})
            self.assertEqual(resposta.status_code, 302)
        resposta = self.client.post(reverse("login:password_reset"), {"email": "nao-existe@example.com"})
        self.assertEqual(resposta.status_code, 429)
        self.assertContains(resposta, "Muitas solicitações", status_code=429)

    def test_redefinicao_exige_csrf(self):
        User.objects.create_user(username="ana", password="senha", email="ana@example.com")
        cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(cliente.post(reverse("login:password_reset"), {"email": "ana@example.com"}).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)


class ObterIpClienteTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, remoto, xff):
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = remoto
        if xff is not None:
            request.META["HTTP_X_FORWARDED_FOR"] = xff
        return request

    def test_sem_proxy_usa_remoto_e_ignora_xff(self):
        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "false"}):
            self.assertEqual(obter_ip_cliente(self._request("203.0.113.7", "192.0.2.1")), "203.0.113.7")

    def test_com_proxy_confiavel_usa_primeira_ip_valida_do_xff(self):
        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "true"}):
            self.assertEqual(obter_ip_cliente(self._request("10.0.0.1", "192.0.2.1, 10.0.0.2")), "192.0.2.1")

    def test_xff_invalido_ignorado_e_usa_remoto(self):
        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "true"}):
            self.assertEqual(obter_ip_cliente(self._request("203.0.113.7", "lixo, 999.1.1.1")), "203.0.113.7")

    def test_sem_xff_usa_remoto(self):
        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "true"}):
            self.assertEqual(obter_ip_cliente(self._request("203.0.113.7", None)), "203.0.113.7")

    def test_render_detectado_automaticamente(self):
        with patch.dict(os.environ, {"RENDER": "true"}, clear=False):
            self.assertEqual(obter_ip_cliente(self._request("10.0.0.1", "198.51.100.4")), "198.51.100.4")

    def test_limite_de_login_por_ips_distintos(self):
        User.objects.create_user(username="ana", password="Nuvem!Laranja927")
        User.objects.create_user(username="bia", password="Nuvem!Laranja927")
        primeiro = Client(REMOTE_ADDR="203.0.113.10")
        segundo = Client(REMOTE_ADDR="203.0.113.20")
        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "true"}):
            for _ in range(5):
                primeiro.post(reverse("login:login"), {"username": "ana", "password": "errada"})
            self.assertEqual(primeiro.post(reverse("login:login"), {"username": "ana", "password": "Nuvem!Laranja927"}).status_code, 429)
            segundo.post(reverse("login:login"), {"username": "bia", "password": "errada"})
            self.assertEqual(segundo.post(reverse("login:login"), {"username": "bia", "password": "Nuvem!Laranja927"}).status_code, 302)


class UsernameCanonicoTests(TestCase):
    def test_cadastro_armazena_username_minusculo(self):
        self.client.post(reverse('cadastro'), {
            'name': 'Ana Maria', 'username': ' AnA ', 'email': 'ana@example.com',
            'password': 'Nuvem!Laranja927', 'password_confirm': 'Nuvem!Laranja927',
            'aceitou_termos': '1',
        })
        self.assertEqual(User.objects.get().username, 'ana')

    def test_login_com_username_em_maiusculas_normaliza(self):
        User.objects.create_user(username='ana', password='Nuvem!Laranja927')
        resposta = self.client.post(reverse('login:login'), {'username': ' ANA ', 'password': 'Nuvem!Laranja927'})
        self.assertRedirects(resposta, reverse('home'))

    def test_duplicado_case_insensitive_rejeitado(self):
        User.objects.create_user(username='Ana', password='senha')
        resposta = self.client.post(reverse('cadastro'), {
            'name': 'Ana', 'username': 'ana', 'email': 'outro@example.com',
            'password': 'Nuvem!Laranja927', 'password_confirm': 'Nuvem!Laranja927',
            'aceitou_termos': '1',
        })
        self.assertTrue(resposta.context['formulario'].errors)
        self.assertEqual(User.objects.count(), 1)
