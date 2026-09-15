from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PreferenciasUsuario


@receiver(post_save, sender=get_user_model())
def criar_preferencias_do_usuario(sender, instance, created, **kwargs):
    if created:
        PreferenciasUsuario.objects.get_or_create(usuario=instance)
