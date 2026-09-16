from django.db import models
from django.utils import timezone


class EventoOutbox(models.Model):
    tipo = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    chave = models.CharField(
        max_length=180,
        unique=True,
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    disponivel_em = models.DateTimeField(default=timezone.now)
    bloqueado_em = models.DateTimeField(null=True, blank=True)
    processado_em = models.DateTimeField(null=True, blank=True)
    descartado_em = models.DateTimeField(null=True, blank=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    ultimo_erro = models.TextField(blank=True)

    class Meta:
        ordering = ["criado_em", "pk"]
        indexes = [
            models.Index(
                fields=["processado_em", "descartado_em", "disponivel_em"],
                name="outbox_pendente_idx",
            ),
            models.Index(
                fields=["bloqueado_em"],
                name="outbox_lock_idx",
            ),
        ]

    @property
    def concluido(self):
        return bool(self.processado_em or self.descartado_em)

    def __str__(self):
        return f"{self.tipo} #{self.pk}"
