from django.conf import settings
from django.db import models
from django.urls import reverse

from posts.models import Comentario, Post


class Notificacao(models.Model):
    class Tipo(models.TextChoices):
        SEGUIDOR = "seguidor", "Novo seguidor"
        CURTIDA = "curtida", "Curtida"
        CURTIDA_COMENTARIO = "curtida_comentario", "Curtida em comentário"
        COMENTARIO = "comentario", "Comentário"
        RESPOSTA = "resposta", "Resposta"
        REPOST = "repost", "Repost"

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
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
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

    def destino(self):
        if self.tipo == self.Tipo.SEGUIDOR:
            return reverse("profile:perfil_publico", args=[self.autor.username])
        if not self.post_id:
            return ""
        url = reverse("posts:detalhe", args=[self.post_id])
        if self.tipo in {
            self.Tipo.COMENTARIO,
            self.Tipo.RESPOSTA,
            self.Tipo.CURTIDA_COMENTARIO,
        } and self.comentario_id:
            return f"{url}#comentario-{self.comentario_id}"
        return url
