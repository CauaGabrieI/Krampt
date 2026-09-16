import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from .handlers import despachar
from .models import EventoOutbox


logger = logging.getLogger(__name__)


def publicar_evento(
    tipo,
    payload,
    *,
    chave=None,
    propagar_eager=True,
):
    defaults = {
        "tipo": tipo,
        "payload": payload,
    }

    if chave:
        evento, _ = EventoOutbox.objects.get_or_create(
            chave=chave,
            defaults=defaults,
        )
    else:
        evento = EventoOutbox.objects.create(**defaults)

    if settings.OUTBOX_EAGER and not evento.concluido:
        processar_evento(
            evento.pk,
            propagar=propagar_eager,
        )
        evento.refresh_from_db()

    return evento


def enfileirar_email(
    destinatario,
    assunto,
    texto,
    *,
    html="",
    chave=None,
):
    destinatarios = (
        [destinatario]
        if isinstance(destinatario, str)
        else list(destinatario)
    )
    return publicar_evento(
        "email.enviar",
        {
            "para": destinatarios,
            "assunto": assunto,
            "texto": texto,
            "html": html,
            "de": settings.DEFAULT_FROM_EMAIL,
        },
        chave=chave,
    )


def enfileirar_exclusao_arquivos(
    nomes,
    *,
    chave=None,
):
    nomes = sorted({nome for nome in nomes if nome})
    if not nomes:
        return None

    return publicar_evento(
        "storage.excluir",
        {"nomes": nomes},
        chave=chave,
        propagar_eager=False,
    )


def _registrar_sucesso(evento):
    EventoOutbox.objects.filter(
        pk=evento.pk,
        processado_em__isnull=True,
        descartado_em__isnull=True,
    ).update(
        processado_em=timezone.now(),
        bloqueado_em=None,
        ultimo_erro="",
        payload={},
    )


def _registrar_falha(evento, erro):
    agora = timezone.now()
    max_tentativas = settings.OUTBOX_MAX_ATTEMPTS
    mensagem = f"{type(erro).__name__}: {erro}"[:2000]

    if evento.tentativas >= max_tentativas:
        EventoOutbox.objects.filter(pk=evento.pk).update(
            descartado_em=agora,
            bloqueado_em=None,
            ultimo_erro=mensagem,
            payload={},
        )
        logger.error(
            "Evento Outbox %s descartado após %s tentativas: %s",
            evento.pk,
            evento.tentativas,
            mensagem,
        )
        return

    atraso = min(
        settings.OUTBOX_RETRY_MAX_SECONDS,
        2 ** min(max(evento.tentativas, 1), 10),
    )
    EventoOutbox.objects.filter(pk=evento.pk).update(
        bloqueado_em=None,
        disponivel_em=agora + timedelta(seconds=atraso),
        ultimo_erro=mensagem,
    )
    logger.warning(
        "Evento Outbox %s falhou; nova tentativa em %ss: %s",
        evento.pk,
        atraso,
        mensagem,
    )


def processar_evento(evento_id, *, propagar=False):
    evento = EventoOutbox.objects.get(pk=evento_id)
    if evento.concluido:
        return True

    if evento.tentativas == 0:
        EventoOutbox.objects.filter(pk=evento.pk).update(
            tentativas=1,
            bloqueado_em=timezone.now(),
        )
        evento.tentativas = 1

    try:
        despachar(evento)
    except Exception as erro:
        _registrar_falha(evento, erro)
        if propagar:
            raise
        return False

    _registrar_sucesso(evento)
    return True


def _reivindicar_proximo():
    agora = timezone.now()
    expirado_em = agora - timedelta(
        seconds=settings.OUTBOX_LEASE_SECONDS
    )

    with transaction.atomic():
        queryset = EventoOutbox.objects.filter(
            processado_em__isnull=True,
            descartado_em__isnull=True,
            disponivel_em__lte=agora,
        ).filter(
            Q(bloqueado_em__isnull=True)
            | Q(bloqueado_em__lte=expirado_em)
        )

        if connection.features.has_select_for_update:
            if connection.features.has_select_for_update_skip_locked:
                queryset = queryset.select_for_update(skip_locked=True)
            else:
                queryset = queryset.select_for_update()

        evento = queryset.order_by("criado_em", "pk").first()
        if evento is None:
            return None

        evento.bloqueado_em = agora
        evento.tentativas += 1
        evento.save(
            update_fields=["bloqueado_em", "tentativas"]
        )
        return evento


def processar_proximo():
    evento = _reivindicar_proximo()
    if evento is None:
        return None

    try:
        despachar(evento)
    except Exception as erro:
        _registrar_falha(evento, erro)
        return False

    _registrar_sucesso(evento)
    return evento
