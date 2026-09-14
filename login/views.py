from smtplib import SMTPException

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_not_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .forms import CadastroForm, LoginForm, VerificacaoForm, normalizar_usuario
from .models import VerificacaoEmail
from .services import (
    bloqueio_ativo, conferir_codigo, emitir_codigo, limpar_falhas, mascarar_email,
    registrar_falha,
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
    identidade = normalizar_usuario(request.POST.get('username', '')) if request.method == 'POST' else ''
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
            usuario = User.objects.filter(username__iexact=identidade, is_active=False).first()
            if usuario and usuario.check_password(request.POST['password']) and VerificacaoEmail.objects.filter(usuario=usuario, verificado_em__isnull=True).exists():
                request.session['verificacao_usuario_id'] = usuario.pk
                limpar_falhas(request, 'login-usuario', identidade)
                return redirect('verificar_email')
            registrar_falha(request, 'login-ip', max_tentativas=20)
            registrar_falha(request, 'login-usuario', identidade)
    return render(request, 'login.html', {
        'formulario': formulario,
        'email_verificado': request.session.pop('email_verificado', False),
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

    formulario = VerificacaoForm(request.POST if request.method == 'POST' and request.POST.get('acao') != 'reenviar' else None)
    contexto = {
        'formulario': formulario,
        'email_mascarado': mascarar_email(verificacao_pendente.usuario.email),
    }
    if request.method == 'POST':
        if bloqueio_ativo(request, 'verificar-ip'):
            return _muitos_pedidos('verificar_email.html', request, formulario)
        if request.POST.get('acao') == 'reenviar':
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
        elif request.POST.get('acao') != 'reenviar':
            registrar_falha(request, 'verificar-ip', max_tentativas=20)
    return render(request, 'verificar_email.html', contexto)
