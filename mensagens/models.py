from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Conversa(models.Model):
    chave = models.CharField(max_length=45, unique=True, null=True, blank=True, editable=False)
    participantes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="conversas"
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em", "-pk"]

    def __str__(self):
        return f"Conversa {self.pk}"

    def outra_pessoa(self, usuario):
        return self.participantes.exclude(pk=usuario.pk).first()

    def para_exibir_para(self, usuario):
        outra = self.outra_pessoa(usuario)
        ultima = self.mensagens.order_by("-criada_em", "-pk").first()
        return {
            "conversa": self,
            "outra_pessoa": outra,
            "ultima_mensagem": ultima,
            "nao_lidas": self.mensagens.filter(lida=False)
            .exclude(autor=usuario)
            .count(),
        }


class Mensagem(models.Model):
    conversa = models.ForeignKey(
        Conversa, related_name="mensagens", on_delete=models.CASCADE
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="mensagens_enviadas",
        on_delete=models.CASCADE,
    )
    conteudo = models.CharField(max_length=280)
    criada_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)
    chave_idempotencia = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        ordering = ["criada_em", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["autor", "chave_idempotencia"],
                condition=models.Q(chave_idempotencia__isnull=False),
                name="mensagem_idempotencia_unica",
            ),
        ]

    def __str__(self):
        return f"{self.autor.username}: {self.conteudo[:40]}"

    def clean(self):
        super().clean()
        if not self.conteudo.strip():
            raise ValidationError({"conteudo": "A mensagem não pode estar vazia."})
