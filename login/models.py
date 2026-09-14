from django.conf import settings
from django.db import models


class VerificacaoEmail(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="verificacao_email"
    )
    codigo_hash = models.CharField(max_length=64, blank=True)
    expira_em = models.DateTimeField(null=True, blank=True)
    verificado_em = models.DateTimeField(null=True, blank=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    bloqueado_ate = models.DateTimeField(null=True, blank=True)
    ultimo_envio_em = models.DateTimeField(null=True, blank=True)
    janela_reenvio_em = models.DateTimeField(null=True, blank=True)
    reenvios_na_janela = models.PositiveSmallIntegerField(default=0)


class LimiteAutenticacao(models.Model):
    chave = models.CharField(max_length=64, unique=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    janela_iniciada_em = models.DateTimeField()
    bloqueado_ate = models.DateTimeField(null=True, blank=True)

# Create your models here.
