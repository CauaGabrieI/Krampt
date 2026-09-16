import ipaddress
import os
import secrets
from datetime import timedelta
from hmac import compare_digest

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import salted_hmac

from outbox.services import enfileirar_email

from .models import LimiteAutenticacao, VerificacaoEmail


TEMPO_CODIGO = timedelta(minutes=10)
JANELA_TENTATIVAS = timedelta(minutes=15)
JANELA_REENVIO = timedelta(hours=1)
INTERVALO_REENVIO = timedelta(seconds=60)


def _resumo(valor, proposito):
    return salted_hmac(f"krampt.{proposito}", valor, algorithm="sha256").hexdigest()


def obter_ip_cliente(request):
    """IP real do cliente, considerando proxies confiáveis somente quando ativado.

    Fora de proxy, X-Forwarded-For não é confiável e é ignorado: usa-se o
    REMOTE_ADDR fornecido pelo servidor. Com TRUST_PROXY_HEADERS=true (ou no
    Render, detectado automaticamente), o primeiro endereço válido de
    X-Forwarded-For é usado como IP do cliente.
    """
    ip_remoto = request.META.get("REMOTE_ADDR", "desconhecido")
    proxy_confiavel = bool(os.environ.get("RENDER")) or os.environ.get(
        "TRUST_PROXY_HEADERS", "false"
    ).lower() == "true"
    if not proxy_confiavel:
        return ip_remoto
    for origem in request.META.get("HTTP_X_FORWARDED_FOR", "").split(","):
        candidato = origem.strip()
        if not candidato:
            continue
        try:
            ipaddress.ip_address(candidato)
        except ValueError:
            continue
        return candidato
    return ip_remoto


def _chave_limite(request, proposito, identidade=""):
    valor = (
        obter_ip_cliente(request)
        if not identidade
        else identidade.casefold()
    )
    return _resumo(f"{proposito}:{valor}", "limite")


def mascarar_email(email):
    if not email or "@" not in email:
        return email
    local, dominio = email.split("@", 1)
    return f"{local[0]}***@{dominio}" if local else f"***@{dominio}"


def _enviar_email(destinatario, assunto, contexto, *, chave=None):
    texto = render_to_string(
        "emails/verificacao_email.txt",
        contexto,
    ).strip()
    html = render_to_string(
        "emails/verificacao_email.html",
        contexto,
    ).strip()
    return enfileirar_email(
        destinatario,
        assunto,
        texto,
        html=html,
        chave=chave,
    )


def bloqueio_ativo(request, proposito, identidade=""):
    chave = _chave_limite(request, proposito, identidade)
    limite = LimiteAutenticacao.objects.filter(chave=chave).first()
    return bool(limite and limite.bloqueado_ate and limite.bloqueado_ate > timezone.now())


def registrar_falha(request, proposito, identidade="", max_tentativas=5):
    agora = timezone.now()
    chave = _chave_limite(request, proposito, identidade)
    with transaction.atomic():
        limite, _ = LimiteAutenticacao.objects.select_for_update().get_or_create(
            chave=chave, defaults={"janela_iniciada_em": agora}
        )
        if agora - limite.janela_iniciada_em >= JANELA_TENTATIVAS:
            limite.janela_iniciada_em = agora
            limite.tentativas = 0
            limite.bloqueado_ate = None
        limite.tentativas += 1
        if limite.tentativas >= max_tentativas:
            limite.bloqueado_ate = agora + JANELA_TENTATIVAS
        limite.save(update_fields=["janela_iniciada_em", "tentativas", "bloqueado_ate"])


def limpar_falhas(request, proposito, identidade=""):
    LimiteAutenticacao.objects.filter(
        chave=_chave_limite(request, proposito, identidade)
    ).delete()


def emitir_codigo(verificacao):
    with transaction.atomic():
        verificacao = (
            VerificacaoEmail.objects.select_for_update()
            .select_related("usuario")
            .get(pk=verificacao.pk)
        )
        agora = timezone.now()
        if (
            verificacao.ultimo_envio_em
            and agora - verificacao.ultimo_envio_em < INTERVALO_REENVIO
        ):
            return "aguarde"
        if (
            not verificacao.janela_reenvio_em
            or agora - verificacao.janela_reenvio_em >= JANELA_REENVIO
        ):
            verificacao.janela_reenvio_em = agora
            verificacao.reenvios_na_janela = 0
        if (
            verificacao.ultimo_envio_em
            and verificacao.reenvios_na_janela >= 3
        ):
            return "limite"

        codigo = f"{secrets.randbelow(1_000_000):06d}"
        novo_hash = _resumo(
            f"{verificacao.usuario_id}:{codigo}",
            "codigo-email",
        )
        while novo_hash == verificacao.codigo_hash:
            codigo = f"{secrets.randbelow(1_000_000):06d}"
            novo_hash = _resumo(
                f"{verificacao.usuario_id}:{codigo}",
                "codigo-email",
            )

        ja_enviado = bool(verificacao.ultimo_envio_em)
        verificacao.codigo_hash = novo_hash
        verificacao.expira_em = agora + TEMPO_CODIGO
        verificacao.ultimo_envio_em = agora
        verificacao.reenvios_na_janela += 1 if ja_enviado else 0
        if (
            not verificacao.bloqueado_ate
            or verificacao.bloqueado_ate <= agora
        ):
            verificacao.tentativas = 0
            verificacao.bloqueado_ate = None
        verificacao.save()

        _enviar_email(
            verificacao.usuario.email,
            "Seu código de verificação do Krampt",
            {"codigo": codigo},
            chave=(
                f"verificacao-email:"
                f"{verificacao.usuario_id}:{novo_hash}"
            ),
        )

    return "enviado"


def conferir_codigo(verificacao, codigo):
    agora = timezone.now()
    if verificacao.bloqueado_ate and verificacao.bloqueado_ate > agora:
        return "limite"
    if not verificacao.codigo_hash or verificacao.verificado_em:
        return "invalido"
    if not verificacao.expira_em or verificacao.expira_em <= agora:
        return "expirado"
    esperado = _resumo(f"{verificacao.usuario_id}:{codigo}", "codigo-email")
    if not compare_digest(esperado, verificacao.codigo_hash):
        verificacao.tentativas += 1
        if verificacao.tentativas >= 5:
            verificacao.bloqueado_ate = agora + JANELA_TENTATIVAS
        verificacao.save(update_fields=["tentativas", "bloqueado_ate"])
        return "limite" if verificacao.bloqueado_ate else "invalido"
    verificacao.codigo_hash = ""
    verificacao.expira_em = None
    verificacao.verificado_em = agora
    verificacao.tentativas = 0
    verificacao.bloqueado_ate = None
    verificacao.save(update_fields=["codigo_hash", "expira_em", "verificado_em", "tentativas", "bloqueado_ate"])
    verificacao.usuario.is_active = True
    verificacao.usuario.save(update_fields=["is_active"])
    return "verificado"
