import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from configuracoes.services import excluir_conta_com_limpeza
from outbox.services import enfileirar_email

from .forms import AdminExcluirUsuarioForm, TesteEmailForm


logger = logging.getLogger(__name__)
User = get_user_model()
DELETE_USER_PERMISSION = f"{User._meta.app_label}.delete_{User._meta.model_name}"


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
            enfileirar_email(
                formulario.cleaned_data["email"],
                "Teste de e-mail do Krampt",
                (
                    "Este é um teste de envio de e-mail do Krampt pela "
                    "Transactional Outbox. Nenhuma ação é necessária."
                ),
            )
        except Exception as erro:
            logger.warning(
                "Falha ao enfileirar e-mail de teste do Krampt (%s)",
                type(erro).__name__,
            )
            contexto["erro_envio"] = (
                "Não foi possível colocar o teste na fila da Outbox. "
                "Confira os logs do servidor e tente novamente."
            )
        else:
            contexto["sucesso"] = (
                (
                    "Teste colocado na fila da Outbox. O worker registrará "
                    "a mensagem no console em vez de entregá-la na caixa de entrada."
                )
                if modo_console
                else (
                    "E-mail colocado na fila da Outbox. O worker fará o envio. "
                    "Confira a caixa de entrada e o spam."
                )
            )

    return render(request, "testar_email.html", contexto)


@login_required
@sensitive_post_parameters("senha_admin")
@require_http_methods(["GET", "POST"])
def apagar_usuarios_view(request):
    if (
        not request.user.is_active
        or not request.user.is_staff
        or not request.user.has_perm(DELETE_USER_PERMISSION)
    ):
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
