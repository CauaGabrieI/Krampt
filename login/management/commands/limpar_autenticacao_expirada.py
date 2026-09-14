import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from login.models import LimiteAutenticacao

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Remove contas nunca verificadas e limites de autenticação antigos, "
        "mantendo o banco enxuto. Nenhuma conta ativa é removida."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prazo-horas",
            type=int,
            default=24,
            help="Idade mínima (em horas) para considerar algo expirado. Padrão: 24.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas informa o que seria removido, sem alterar o banco.",
        )

    def handle(self, *args, **options):
        prazo = timedelta(hours=options["prazo_horas"])
        corte = timezone.now() - prazo
        executar = not options["dry_run"]

        usuarios_antigos = User.objects.filter(
            is_active=False,
            date_joined__lt=corte,
            verificacao_email__verificado_em__isnull=True,
        )
        limites_antigos = LimiteAutenticacao.objects.filter(
            janela_iniciada_em__lt=corte,
            bloqueado_ate__isnull=True,
        ) | LimiteAutenticacao.objects.filter(
            janela_iniciada_em__lt=corte,
            bloqueado_ate__lt=timezone.now(),
        )

        total_usuarios = usuarios_antigos.count()
        total_limites = limites_antigos.count()
        acao = "A ser removido" if not executar else "Removendo"
        self.stdout.write(
            f"{acao}: {total_usuarios} conta(s) de usuário nunca verificada(s) "
            f"e {total_limites} limite(s) de autenticação antigo(s)."
        )

        if not executar:
            return

        with transaction.atomic():
            usuarios_excluidos = list(usuarios_antigos.values_list("pk", flat=True))
            limites_excluidos = list(limites_antigos.values_list("pk", flat=True))
            if usuarios_excluidos:
                User.objects.filter(pk__in=usuarios_excluidos).delete()
            if limites_excluidos:
                LimiteAutenticacao.objects.filter(pk__in=limites_excluidos).delete()
        logger.info(
            "limpar_autenticacao_expirada removeu %d contas e %d limites",
            len(usuarios_excluidos),
            len(limites_excluidos),
        )