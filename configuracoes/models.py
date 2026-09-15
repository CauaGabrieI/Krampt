from django.conf import settings
from django.db import models


class PreferenciasUsuario(models.Model):
    class PermissaoMensagem(models.TextChoices):
        TODOS = "todos", "Todas as pessoas"
        SEGUINDO = "seguindo", "Somente pessoas que sigo"
        NINGUEM = "ninguem", "Ninguém"

    class Tema(models.TextChoices):
        SISTEMA = "sistema", "Sistema"
        ESCURO = "escuro", "Escuro"
        CLARO = "claro", "Claro"

    class TamanhoFonte(models.TextChoices):
        PEQUENA = "pequena", "Pequena"
        PADRAO = "padrao", "Padrão"
        GRANDE = "grande", "Grande"

    class Densidade(models.TextChoices):
        CONFORTAVEL = "confortavel", "Confortável"
        COMPACTA = "compacta", "Compacta"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferencias",
    )
    desativada_em = models.DateTimeField(null=True, blank=True)
    token_reativacao_hash = models.CharField(max_length=64, blank=True)
    token_reativacao_expira_em = models.DateTimeField(null=True, blank=True)
    reativacao_ultimo_envio_em = models.DateTimeField(null=True, blank=True)
    reativacao_janela_envio_em = models.DateTimeField(null=True, blank=True)
    reativacao_envios_na_janela = models.PositiveSmallIntegerField(default=0)

    permitir_novas_conversas = models.BooleanField(default=True)
    mensagens_de = models.CharField(
        max_length=12,
        choices=PermissaoMensagem.choices,
        default=PermissaoMensagem.TODOS,
    )
    notificacoes_site = models.BooleanField(default=True)
    notificar_seguidores = models.BooleanField(default=True)
    notificar_curtidas = models.BooleanField(default=True)
    notificar_comentarios = models.BooleanField(default=True)
    notificar_respostas = models.BooleanField(default=True)
    notificar_reposts = models.BooleanField(default=True)
    notificar_mensagens = models.BooleanField(default=True)

    tema = models.CharField(max_length=8, choices=Tema.choices, default=Tema.SISTEMA)
    tamanho_fonte = models.CharField(
        max_length=8,
        choices=TamanhoFonte.choices,
        default=TamanhoFonte.PADRAO,
    )
    reduzir_animacoes = models.BooleanField(default=False)
    densidade = models.CharField(
        max_length=11,
        choices=Densidade.choices,
        default=Densidade.CONFORTAVEL,
    )

    def __str__(self):
        return f"Configurações de @{self.usuario.username}"
