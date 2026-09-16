from django.db import models
from django.conf import settings

class Hashtag(models.Model):
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["nome"]

class Post(models.Model):
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    conteudo = models.TextField(blank=True)

    imagem = models.ImageField(upload_to="imagens_posts/", blank=True)
    audio = models.FileField(upload_to="audios_posts/", blank=True)

    original = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="republicacoes",
        null=True,
        blank=True,
    )

    curtidas = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="posts_curtidos",
        blank=True,
    )
    salvos_por = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="posts_salvos",
        blank=True,
    )
    hashtags = models.ManyToManyField(Hashtag, related_name="posts", blank=True)

    criado_em = models.DateTimeField(
        auto_now_add=True
    )
    editado_em = models.DateTimeField(null=True, blank=True)
    chave_idempotencia = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        editable=False,
    )

    @property
    def fotos(self):
        return ([self.imagem] if self.imagem else []) + [
            item.imagem for item in self.imagens_adicionais.all()
        ]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["autor", "original"],
                condition=models.Q(original__isnull=False),
                name="uma_republicacao_por_usuario",
            ),
            models.UniqueConstraint(
                fields=["autor", "chave_idempotencia"],
                condition=models.Q(chave_idempotencia__isnull=False),
                name="post_idempotencia_unica",
            ),
        ]


class ImagemPost(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="imagens_adicionais")
    imagem = models.ImageField(upload_to="imagens_posts/")

    class Meta:
        ordering = ["pk"]


class Comentario(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comentarios_feitos",
    )
    resposta_para = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="respostas",
        null=True,
        blank=True,
    )
    conteudo = models.TextField(max_length=280)
    imagem = models.ImageField(upload_to="imagens_comentarios/", blank=True)
    audio = models.FileField(upload_to="audios_comentarios/", blank=True)
    hashtags = models.ManyToManyField(Hashtag, related_name="comentarios", blank=True)
    curtidas = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="comentarios_curtidos",
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    chave_idempotencia = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        ordering = ["criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["autor", "chave_idempotencia"],
                condition=models.Q(chave_idempotencia__isnull=False),
                name="comentario_idempotencia_unica",
            ),
        ]


class PostSemInteresse(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts_sem_interesse",
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="ignorado_por")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "post"], name="post_sem_interesse_unico"),
        ]


class UsuarioSilenciado(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usuarios_silenciados",
    )
    silenciado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="silenciado_por",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "silenciado"], name="usuario_silenciado_unico"),
            models.CheckConstraint(
                condition=~models.Q(usuario=models.F("silenciado")),
                name="usuario_nao_silencia_a_si_mesmo",
            ),
        ]


class UsuarioBloqueado(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usuarios_bloqueados",
    )
    bloqueado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bloqueado_por",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "bloqueado"], name="usuario_bloqueado_unico"),
            models.CheckConstraint(
                condition=~models.Q(usuario=models.F("bloqueado")),
                name="usuario_nao_bloqueia_a_si_mesmo",
            ),
        ]


class DenunciaPost(models.Model):
    class Motivo(models.TextChoices):
        SPAM = "spam", "Spam"
        ASSEDIO = "assedio", "Assédio"
        ODIO = "odio", "Discurso de ódio"
        SEXUAL = "sexual", "Conteúdo sexual"
        VIOLENCIA = "violencia", "Violência"
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
        related_name="denuncias_enviadas",
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="denuncias")
    motivo = models.CharField(max_length=32, choices=Motivo.choices)
    detalhes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["denunciante", "post"], name="denuncia_post_unica"),
        ]
