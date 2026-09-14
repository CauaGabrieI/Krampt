import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import TesteEmailForm


logger = logging.getLogger(__name__)


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
