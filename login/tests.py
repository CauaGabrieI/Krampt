from django.contrib.auth import get_user_model
from django.core import mail
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import re
from unittest.mock import patch

from login.models import LimiteAutenticacao, VerificacaoEmail
from login.services import mascarar_email
from django.core import management
from io import StringIO

User = get_user_model()


class CadastroTests(TestCase):
    def dados(self, **alteracoes):
        dados = dict(name='  Ana   Maria  ', username=' an a\t ', email=' ANA@EXAMPLE.COM ', password='Nuvem!Laranja927', password_confirm='Nuvem!Laranja927')
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

    def test_bloqueia_login_apos_tentativas_excessivas(self):
        for _ in range(5):
            self.client.post(reverse('login:login'), {'username': 'ana', 'password': 'errada'})
        response = self.client.post(reverse('login:login'), {'username': 'ana', 'password': 'Nuvem!Laranja927'})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Tentativas excessivas', status_code=429)
        self.assertNotIn('_auth_user_id', self.client.session)


@override_settings(MAILERS={
    'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}
})
class VerificacaoEmailTests(TestCase):
    def cadastrar(self, client=None, username='ana', email='ana@example.com'):
        client = client or self.client
        response = client.post(reverse('cadastro'), {
            'name': 'Ana Maria', 'username': username, 'email': email,
            'password': 'Nuvem!Laranja927', 'password_confirm': 'Nuvem!Laranja927',
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
