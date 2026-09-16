from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives


def _enviar_email(payload):
    destinatarios = payload.get("para") or []
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]

    mensagem = EmailMultiAlternatives(
        payload["assunto"],
        payload.get("texto", ""),
        payload.get("de") or settings.DEFAULT_FROM_EMAIL,
        destinatarios,
    )
    html = payload.get("html")
    if html:
        mensagem.attach_alternative(html, "text/html")

    if mensagem.send() != 1:
        raise OSError("O serviço de e-mail não confirmou o envio.")


def _excluir_arquivos(payload):
    for nome in payload.get("nomes", []):
        if nome:
            default_storage.delete(nome)


HANDLERS = {
    "email.enviar": _enviar_email,
    "storage.excluir": _excluir_arquivos,
}


def despachar(evento):
    try:
        handler = HANDLERS[evento.tipo]
    except KeyError as erro:
        raise ValueError(
            f"Tipo de evento Outbox sem handler: {evento.tipo}"
        ) from erro

    handler(evento.payload)
