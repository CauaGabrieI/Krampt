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

    class Meta:
        ordering = ["criado_em"]
