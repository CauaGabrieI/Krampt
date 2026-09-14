from django.db import models
from django.conf import settings


class Perfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    foto = models.ImageField(upload_to="fotos_perfil/", blank=True)
    banner = models.ImageField(upload_to="banners_perfil/", blank=True)
    biografia = models.CharField(max_length=160, blank=True)
    seguindo = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="seguidores",
        symmetrical=False,
        blank=True,
    )
    
