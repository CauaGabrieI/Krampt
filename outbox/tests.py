from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import EventoOutbox
from .services import enfileirar_email, processar_evento, publicar_evento


@override_settings(
    OUTBOX_EAGER=False,
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend"
        }
    },
)
class OutboxTests(TestCase):
    def test_evento_fica_no_mesmo_rollback_da_transacao(self):
        try:
            with transaction.atomic():
                publicar_evento(
                    "email.enviar",
                    {
                        "para": ["ana@example.com"],
                        "assunto": "Teste",
                        "texto": "Olá",
                        "html": "",
                        "de": "Krampt <nao-responda@krampt.local>",
                    },
                )
                raise RuntimeError("rollback")
        except RuntimeError:
            pass

        self.assertFalse(EventoOutbox.objects.exists())

    def test_email_e_processado_e_payload_sensivel_e_redigido(self):
        evento = enfileirar_email(
            "ana@example.com",
            "Assunto",
            "Código 123456",
            html="<p>Código 123456</p>",
            chave="teste-email-1",
        )
        self.assertEqual(len(mail.outbox), 0)

        self.assertTrue(processar_evento(evento.pk))

        self.assertEqual(len(mail.outbox), 1)
        evento.refresh_from_db()
        self.assertIsNotNone(evento.processado_em)
        self.assertEqual(evento.payload, {})

    def test_chave_idempotente_nao_duplica_evento(self):
        primeiro = enfileirar_email(
            "ana@example.com",
            "Assunto",
            "A",
            chave="email-idempotente",
        )
        segundo = enfileirar_email(
            "ana@example.com",
            "Assunto",
            "A",
            chave="email-idempotente",
        )

        self.assertEqual(primeiro.pk, segundo.pk)
        self.assertEqual(EventoOutbox.objects.count(), 1)

    def test_falha_agenda_retry_sem_apagar_payload(self):
        evento = publicar_evento(
            "email.enviar",
            {
                "para": ["ana@example.com"],
                "assunto": "Teste",
                "texto": "segredo temporário",
                "html": "",
                "de": "Krampt <nao-responda@krampt.local>",
            },
        )

        with patch(
            "outbox.handlers.EmailMultiAlternatives.send",
            side_effect=OSError("SMTP fora"),
        ):
            self.assertFalse(processar_evento(evento.pk))

        evento.refresh_from_db()
        self.assertIsNone(evento.processado_em)
        self.assertIsNone(evento.descartado_em)
        self.assertGreater(evento.disponivel_em, timezone.now())
        self.assertIn("SMTP fora", evento.ultimo_erro)
        self.assertTrue(evento.payload)

    def test_management_command_processa_fila(self):
        enfileirar_email(
            "ana@example.com",
            "Assunto",
            "Olá",
        )

        call_command(
            "process_outbox",
            "--once",
            stdout=StringIO(),
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            EventoOutbox.objects.filter(
                processado_em__isnull=False
            ).count(),
            1,
        )

    def test_lease_expirada_pode_ser_reivindicada(self):
        evento = publicar_evento(
            "email.enviar",
            {
                "para": ["ana@example.com"],
                "assunto": "Teste",
                "texto": "Olá",
                "html": "",
                "de": "Krampt <nao-responda@krampt.local>",
            },
        )
        evento.bloqueado_em = timezone.now() - timedelta(minutes=10)
        evento.save(update_fields=["bloqueado_em"])

        call_command(
            "process_outbox",
            "--once",
            stdout=StringIO(),
        )

        evento.refresh_from_db()
        self.assertIsNotNone(evento.processado_em)
