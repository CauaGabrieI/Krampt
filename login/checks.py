import os

from django.conf import settings
from django.core.checks import Error, Warning, register


@register(tags=("email",))
def verificar_email_em_producao(app_configs, **kwargs):
    erros = []
    if settings.DEBUG:
        return erros
    mailers = settings.MAILERS.get("default", {})
    backend = mailers.get("BACKEND", "")
    if backend.endswith("smtp.EmailBackend") and not os.environ.get("EMAIL_HOST"):
        erros.append(
            Error(
                "EMAIL_HOST não está definido em produção.",
                hint="Defina EMAIL_HOST (e, se necessário, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, EMAIL_USE_SSL e EMAIL_TIMEOUT) no .env ou nas variáveis de ambiente do servidor.",
                id="krampt.E001",
            )
        )
    opcoes = mailers.get("OPTIONS", {})
    if opcoes.get("use_tls") and opcoes.get("use_ssl"):
        erros.append(
            Error(
                "EMAIL_USE_TLS e EMAIL_USE_SSL não podem ser ativados ao mesmo tempo.",
                hint="Ative somente um deles no .env ou nas variáveis de ambiente.",
                id="krampt.E002",
            )
        )
    return erros


@register(tags=("username",))
def verificar_usernames_canonicos(app_configs, **kwargs):
    """Reporta (sem alterar) usuários com nome fora do padrão minúsculo."""
    if app_configs is not None:
        return []
    try:
        from django.contrib.auth import get_user_model
        from django.db.models.functions import Lower

        User = get_user_model()
        nao_canonicos = User.objects.exclude(username=Lower("username")).count()
    except Exception:
        return []
    if not nao_canonicos:
        return []
    return [
        Warning(
            f"{nao_canonicos} usuário(s) com nome de usuário fora do padrão minúsculo.",
            hint="O cadastro agora normaliza usuários para minúsculas. Antes de padronizar, verifique colisões case-insensitive e converta manualmente os nomes existentes.",
            id="krampt.W003",
        )
    ]