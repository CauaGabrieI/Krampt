from django.db import models
from django.conf import settings


class Perfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    post_fixado = models.ForeignKey(
        "posts.Post",
        on_delete=models.SET_NULL,
        related_name="fixado_em_perfis",
        null=True,
        blank=True,
    )
    foto = models.ImageField(upload_to="fotos_perfil/", blank=True)
    banner = models.ImageField(upload_to="banners_perfil/", blank=True)
    biografia = models.CharField(max_length=160, blank=True)
    verificado = models.BooleanField(default=False)
    seguindo = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="seguidores",
        symmetrical=False,
        blank=True,
    )

class DenunciaUsuario(models.Model):
    class Motivo(models.TextChoices):
        SPAM = "spam", "Spam"
        ASSEDIO = "assedio", "Assédio"
        ODIO = "odio", "Discurso de ódio"
        FALSA_IDENTIDADE = "falsa_identidade", "Falsa identidade"
        SEXUAL = "sexual", "Conteúdo sexual"
        VIOLENCIA = "violencia", "Violência ou ameaça"
        INFORMACAO_PESSOAL = "informacao_pessoal", "Informação pessoal"
        OUTRO = "outro", "Outro"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EM_ANALISE = "em_analise", "Em análise"
        RESOLVIDA = "resolvida", "Resolvida"
        RECUSADA = "recusada", "Recusada"

    denunciante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="denuncias_de_perfil_enviadas",
    )
    alvo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="denuncias_de_perfil_recebidas",
    )
    motivo = models.CharField(max_length=32, choices=Motivo.choices)
    detalhes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["denunciante", "alvo"],
                name="denuncia_usuario_unica",
            ),
            models.CheckConstraint(
                condition=~models.Q(denunciante=models.F("alvo")),
                name="usuario_nao_denuncia_a_si_mesmo",
            ),
        ]
