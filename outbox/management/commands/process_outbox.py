import time

from django.conf import settings
from django.core.management.base import BaseCommand

from outbox.services import processar_proximo


class Command(BaseCommand):
    help = "Processa a Transactional Outbox do Krampt."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Processa eventos disponíveis e encerra.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Máximo de eventos por ciclo no modo --once.",
        )

    def handle(self, *args, **options):
        if options["once"]:
            processados = 0
            while processados < max(options["limit"], 1):
                resultado = processar_proximo()
                if resultado is None:
                    break
                processados += 1
                if resultado is not False:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Evento Outbox {resultado.pk} processado com sucesso: "
                            f"{resultado.tipo}"
                        )
                    )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Outbox: {processados} evento(s) reivindicado(s)."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Worker Outbox iniciado. Ctrl+C para encerrar."
            )
        )
        intervalo = max(settings.OUTBOX_POLL_SECONDS, 0.2)

        try:
            while True:
                resultado = processar_proximo()
                if resultado is None:
                    time.sleep(intervalo)
                    continue
                if resultado is not False:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Evento Outbox {resultado.pk} processado com sucesso: "
                            f"{resultado.tipo}"
                        )
                    )
        except KeyboardInterrupt:
            self.stdout.write("Worker Outbox encerrado.")
