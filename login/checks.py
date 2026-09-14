import os

from django.conf import settings
from django.core.checks import Error, register


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