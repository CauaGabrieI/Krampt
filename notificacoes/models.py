from django.conf import settings
from django.db import models

from posts.models import Comentario, Post


class Notificacao(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes_enviadas",
    )
    tipo = models.CharField(max_length=30)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="notificacoes",
        null=True,
        blank=True,
    )
    comentario = models.ForeignKey(
        Comentario,
        on_delete=models.CASCADE,
        related_name="notificacoes",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        indexes = [
            models.Index(fields=["usuario", "lida"]),
        ]