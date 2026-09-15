from smtplib import SMTPException

from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .forms import (
    CadastroForm, LoginForm, RedefinirSenhaForm, TrocarEmailVerificacaoForm,
    VerificacaoForm, normalizar_identidade_login,
)
from .models import VerificacaoEmail
from .services import (
    bloqueio_ativo, conferir_codigo, emitir_codigo, limpar_falhas, mascarar_email,
    registrar_falha,
)
from configuracoes.services import (
    conta_desativada_voluntariamente,
    reativar_por_token,
    solicitar_reativacao,
)


User = get_user_model()


def _muitos_pedidos(template, request, formulario):
    return render(
        request, template,
        {"formulario": formulario, "erro_limite": "Tentativas excessivas. Aguarde 15 minutos e tente novamente."},
        status=429,
    )


@login_not_required
@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    identidade = normalizar_identidade_login(request.POST.get('username', '')) if request.method == 'POST' else ''
    if request.method == 'POST' and (
        bloqueio_ativo(request, 'login-ip') or bloqueio_ativo(request, 'login-usuario', identidade)
    ):
        return _muitos_pedidos('login.html', request, LoginForm(request))
    formulario = LoginForm(request, request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if formulario.is_valid():
            limpar_falhas(request, 'login-usuario', identidade)
            login(request, formulario.usuario)
            destino = request.GET.get('next', '')
            if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(destino)
            return redirect('home')
        if identidade and request.POST.get('password'):
            filtro = Q(username__iexact=identidade)
            if "@" in identidade:
                filtro |= Q(email__iexact=identidade)
            usuario = User.objects.filter(filtro, is_active=False).first()
            if usuario and usuario.check_password(request.POST['password']):
                if conta_desativada_voluntariamente(usuario):
                    request.session["reativacao_usuario_id"] = usuario.pk
                    limpar_falhas(request, 'login-usuario', identidade)
                    return redirect("reativar_conta")
                if VerificacaoEmail.objects.filter(usuario=usuario, verificado_em__isnull=True).exists():
                    request.session['verificacao_usuario_id'] = usuario.pk
                    limpar_falhas(request, 'login-usuario', identidade)
                    return redirect('verificar_email')
            registrar_falha(request, 'login-ip', max_tentativas=20)
            registrar_falha(request, 'login-usuario', identidade)
    return render(request, 'login.html', {
        'formulario': formulario,
        'email_verificado': request.session.pop('email_verificado', False),
        'conta_reativada': request.session.pop('conta_reativada', False),
    })


@login_not_required
@sensitive_post_parameters('password', 'password_confirm')
@require_http_methods(['GET', 'POST'])
def cadastro_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    formulario = CadastroForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and formulario.is_valid():
        try:
            with transaction.atomic():
                usuario = formulario.save()
                verificacao = VerificacaoEmail.objects.create(usuario=usuario)
                emitir_codigo(verificacao)
        except IntegrityError:
            formulario.add_error(None, 'Não foi possível criar a conta com esses dados. Tente outro usuário.')
        except (SMTPException, OSError):
            formulario.add_error(None, 'Não foi possível enviar o código agora. Tente novamente em instantes.')
        else:
            request.session['verificacao_usuario_id'] = usuario.pk
            return redirect('verificar_email')
    return render(request, 'cadastro.html', {'formulario': formulario})


@login_not_required
@sensitive_post_parameters('codigo')
@require_http_methods(['GET', 'POST'])
def verificar_email_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    usuario_id = request.session.get('verificacao_usuario_id')
    verificacao_pendente = (
        VerificacaoEmail.objects.filter(usuario_id=usuario_id, verificado_em__isnull=True)
        .select_related('usuario')
        .first()
    )
    if not usuario_id or not verificacao_pendente:
        request.session.pop('verificacao_usuario_id', None)
        return redirect('cadastro')

    acao = request.POST.get('acao') if request.method == 'POST' else ''
    formulario = VerificacaoForm(request.POST if request.method == 'POST' and not acao else None)
    formulario_email = TrocarEmailVerificacaoForm(
        verificacao_pendente.usuario,
        request.POST if request.method == 'POST' and acao == 'trocar_email' else None,
    )
    contexto = {
        'formulario': formulario,
        'formulario_email': formulario_email,
        'email_mascarado': mascarar_email(verificacao_pendente.usuario.email),
    }
    if request.method == 'POST':
        if bloqueio_ativo(request, 'verificar-ip'):
            return _muitos_pedidos('verificar_email.html', request, formulario)
        if acao == 'reenviar':
            try:
                with transaction.atomic():
                    verificacao = VerificacaoEmail.objects.select_for_update().select_related('usuario').get(usuario_id=usuario_id)
                    resultado = emitir_codigo(verificacao)
            except (SMTPException, OSError):
                contexto['erro'] = 'Não foi possível enviar o código agora. Tente novamente em instantes.'
            else:
                contexto['mensagem' if resultado == 'enviado' else 'erro'] = {
                    'enviado': 'Novo código enviado. Confira seu e-mail.',
                    'aguarde': 'Aguarde 60 segundos antes de solicitar outro código.',
                    'limite': 'Limite de reenvios atingido. Aguarde até uma hora.',
                }[resultado]
                if resultado == 'limite':
                    return render(request, 'verificar_email.html', contexto, status=429)
        elif acao == "trocar_email":
            if formulario_email.is_valid():
                try:
                    with transaction.atomic():
                        verificacao = VerificacaoEmail.objects.select_for_update().select_related('usuario').get(usuario_id=usuario_id)
                        formulario_email.usuario = verificacao.usuario
                        formulario_email.save()
                        verificacao.codigo_hash = ""
                        verificacao.expira_em = None
                        verificacao.verificado_em = None
                        verificacao.tentativas = 0
                        verificacao.bloqueado_ate = None
                        verificacao.ultimo_envio_em = None
                        verificacao.janela_reenvio_em = None
                        verificacao.reenvios_na_janela = 0
                        verificacao.save(
                            update_fields=[
                                "codigo_hash",
                                "expira_em",
                                "verificado_em",
                                "tentativas",
                                "bloqueado_ate",
                                "ultimo_envio_em",
                                "janela_reenvio_em",
                                "reenvios_na_janela",
                            ]
                        )
                        resultado = emitir_codigo(verificacao)
                except (SMTPException, OSError):
                    contexto['erro'] = 'Não foi possível enviar o código agora. Tente novamente em instantes.'
                else:
                    contexto['email_mascarado'] = mascarar_email(verificacao.usuario.email)
                    contexto['mensagem' if resultado == 'enviado' else 'erro'] = {
                        'enviado': 'E-mail alterado. Enviamos um novo código.',
                        'aguarde': 'Aguarde 60 segundos antes de solicitar outro código.',
                        'limite': 'Limite de reenvios atingido. Aguarde até uma hora.',
                    }[resultado]
        elif formulario.is_valid():
            with transaction.atomic():
                verificacao = VerificacaoEmail.objects.select_for_update().select_related('usuario').get(usuario_id=usuario_id)
                resultado = conferir_codigo(verificacao, formulario.cleaned_data['codigo'])
            if resultado == 'verificado':
                request.session.pop('verificacao_usuario_id', None)
                request.session['email_verificado'] = True
                return redirect('login:login')
            registrar_falha(request, 'verificar-ip', max_tentativas=20)
            contexto['erro'] = {
                'invalido': 'Código inválido. Confira os números e tente novamente.',
                'expirado': 'Código expirado. Solicite um novo código.',
                'limite': 'Tentativas excessivas. Aguarde 15 minutos e tente novamente.',
            }[resultado]
            if resultado == 'limite':
                return render(request, 'verificar_email.html', contexto, status=429)
        elif acao not in {'reenviar', 'trocar_email'}:
            registrar_falha(request, 'verificar-ip', max_tentativas=20)
    return render(request, 'verificar_email.html', contexto)


@login_not_required
@sensitive_post_parameters()
@require_http_methods(["GET", "POST"])
def reativar_conta_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    usuario_id = request.session.get("reativacao_usuario_id")
    usuario = User.objects.filter(pk=usuario_id, is_active=False).first()
    if not usuario or not conta_desativada_voluntariamente(usuario):
        request.session.pop("reativacao_usuario_id", None)
        return redirect("login:login")

    contexto = {
        "email_mascarado": mascarar_email(usuario.email),
    }
    if request.method == "POST":
        resultado = solicitar_reativacao(usuario, request)
        if resultado == "enviado":
            contexto["mensagem"] = "Enviamos um link de reativação para o seu e-mail."
        elif resultado in {"aguarde", "limite"}:
            contexto["erro"] = "Um link já foi solicitado recentemente."
            status = 429 if resultado == "limite" else 200
            return render(request, "reativar_conta.html", contexto, status=status)
        else:
            request.session.pop("reativacao_usuario_id", None)
            return redirect("login:login")
    return render(request, "reativar_conta.html", contexto)


@login_not_required
@require_http_methods(["GET"])
def reativar_conta_token_view(request, token):
    if request.user.is_authenticated:
        return redirect("home")
    if reativar_por_token(token):
        request.session.pop("reativacao_usuario_id", None)
        request.session["conta_reativada"] = True
        return redirect("login:login")
    return render(request, "reativar_conta_invalido.html", status=400)


@method_decorator(login_not_required, name="dispatch")
@method_decorator(sensitive_post_parameters(), name="dispatch")
class RedefinirSenhaView(auth_views.PasswordResetView):
    template_name = "password_reset_form.html"
    form_class = RedefinirSenhaForm
    success_url = reverse_lazy("login:password_reset_done")
    email_template_name = "emails/recuperacao_senha.txt"
    html_email_template_name = "emails/recuperacao_senha.html"
    subject_template_name = "emails/recuperacao_senha_subject.txt"
    proposito_limite = "reset-senha-ip"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and bloqueio_ativo(request, self.proposito_limite):
            formulario = self.get_form()
            return render(
                request,
                self.template_name,
                {
                    "formulario": formulario,
                    "erro_limite": "Muitas solicitações. Aguarde 15 minutos e tente novamente.",
                },
                status=429,
            )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        registrar_falha(request, self.proposito_limite, max_tentativas=5)
        return super().post(request, *args, **kwargs)


@method_decorator(login_not_required, name="dispatch")
class RedefinirSenhaDoneView(auth_views.PasswordResetDoneView):
    template_name = "password_reset_done.html"


@method_decorator(login_not_required, name="dispatch")
@method_decorator(sensitive_post_parameters(), name="dispatch")
class RedefinirSenhaConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "password_reset_confirm.html"
    success_url = reverse_lazy("login:password_reset_complete")


@method_decorator(login_not_required, name="dispatch")
class RedefinirSenhaCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "password_reset_complete.html"
