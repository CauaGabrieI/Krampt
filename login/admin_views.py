import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from configuracoes.services import excluir_conta_com_limpeza

from .forms import AdminExcluirUsuarioForm, TesteEmailForm


logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
@require_http_methods(["GET", "POST"])
def testar_email_view(request):
    if not request.user.is_active or not request.user.is_staff:
        raise PermissionDenied

    modo_console = settings.MAILERS["default"]["BACKEND"].endswith("console.EmailBackend")
    formulario = TesteEmailForm(request.POST if request.method == "POST" else None)
    contexto = {"formulario": formulario, "modo_console": modo_console}

    if request.method == "POST" and formulario.is_valid():
        try:
            enviados = send_mail(
                "Teste de e-mail do Krampt",
                "Este é um teste de envio de e-mail do Krampt. Nenhuma ação é necessária.",
                settings.DEFAULT_FROM_EMAIL,
                [formulario.cleaned_data["email"]],
            )
            if enviados != 1:
                raise OSError("O serviço de e-mail não confirmou o envio.")
        except (SMTPException, OSError) as erro:
            logger.warning("Falha ao enviar e-mail de teste do Krampt (%s)", type(erro).__name__)
            contexto["erro_envio"] = "O envio falhou. Confira a configuração de e-mail do servidor e tente novamente."
        else:
            contexto["sucesso"] = (
                "Teste registrado no console do servidor. Nenhum e-mail chegou à caixa de entrada."
                if modo_console
                else "O servidor de e-mail aceitou a mensagem. Confira a caixa de entrada e o spam."
            )

    return render(request, "testar_email.html", contexto)


@login_required
@sensitive_post_parameters("senha_admin")
@require_http_methods(["GET", "POST"])
def apagar_usuarios_view(request):
    if not request.user.is_active or not request.user.is_staff:
        raise PermissionDenied

    termo = request.GET.get("q", "").strip()
    usuarios = User.objects.order_by("username")
    if termo:
        usuarios = usuarios.filter(username__icontains=termo)
    usuarios = usuarios[:50]
    formulario = AdminExcluirUsuarioForm(request.POST if request.method == "POST" else None)

    if request.method == "POST" and formulario.is_valid():
        usuario_id = formulario.cleaned_data["usuario_id"]
        alvo = User.objects.filter(pk=usuario_id).first()
        if not request.user.check_password(formulario.cleaned_data["senha_admin"]):
            messages.error(request, "Senha de admin inválida.")
        elif not alvo:
            messages.error(request, "Usuário não encontrado.")
        elif alvo.pk == request.user.pk:
            messages.error(request, "Você não pode apagar sua própria conta por esta tela.")
        elif formulario.cleaned_data["confirmacao"] != alvo.username:
            messages.error(request, "Confirmação de username inválida.")
        else:
            try:
                excluir_conta_com_limpeza(alvo)
            except Exception:
                messages.error(request, "Não foi possível apagar o usuário agora.")
            else:
                messages.success(request, f"Usuário @{alvo.username} apagado.")
                return redirect("admin_apagar_usuarios")

    return render(
        request,
        "admin_apagar_usuarios.html",
        {"usuarios": usuarios, "termo": termo, "formulario": formulario},
    )
