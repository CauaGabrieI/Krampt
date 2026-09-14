from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Comentario, Hashtag, Post
from .services import hashtags_do_texto


@receiver(post_save, sender=Post)
def sincronizar_hashtags_do_post(sender, instance, **kwargs):
    hashtags = []
    for slug, nome in hashtags_do_texto(instance.conteudo).items():
        hashtag, _ = Hashtag.objects.get_or_create(slug=slug, defaults={"nome": nome})
        if hashtag.nome != nome:
            hashtag.nome = nome
            hashtag.save(update_fields=["nome"])
        hashtags.append(hashtag)
    instance.hashtags.set(hashtags)


@receiver(post_save, sender=Comentario)
def sincronizar_hashtags_do_comentario(sender, instance, **kwargs):
    hashtags = []
    for slug, nome in hashtags_do_texto(instance.conteudo).items():
        hashtag, _ = Hashtag.objects.get_or_create(slug=slug, defaults={"nome": nome})
        hashtags.append(hashtag)
    instance.hashtags.set(hashtags)