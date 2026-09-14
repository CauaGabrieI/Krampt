import logging

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Comentario, Hashtag, ImagemPost, Post
from .services import hashtags_do_texto


logger = logging.getLogger(__name__)

_CAMINHOS = "_arquivos_a_excluir"


def _coletar_arquivos(instance, campos):
    caminhos = getattr(instance, _CAMINHOS, None) or []
    for campo in campos:
        arquivo = getattr(instance, campo)
        nome = getattr(arquivo, "name", "")
        if nome:
            caminhos.append(nome)
    setattr(instance, _CAMINHOS, caminhos)


def _agendar_exclusao_de_arquivos(instance, **kwargs):
    caminhos = getattr(instance, _CAMINHOS, ())
    if not caminhos:
        return

    def excluir():
        for nome in caminhos:
            if not nome:
                continue
            try:
                default_storage.delete(nome)
            except Exception as erro:  # noqa: BLE001
                logger.warning("Falha ao excluir arquivo %s do armazenamento (%s)", nome, erro)

    transaction.on_commit(excluir)


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


@receiver(pre_delete, sender=Post)
def coletar_arquivos_do_post(sender, instance, **kwargs):
    _coletar_arquivos(instance, ("imagem", "audio"))


@receiver(pre_delete, sender=ImagemPost)
def coletar_arquivo_da_imagem_extra(sender, instance, **kwargs):
    _coletar_arquivos(instance, ("imagem",))


@receiver(pre_delete, sender=Comentario)
def coletar_arquivos_do_comentario(sender, instance, **kwargs):
    _coletar_arquivos(instance, ("imagem", "audio"))


@receiver(post_delete, sender=Post)
@receiver(post_delete, sender=ImagemPost)
@receiver(post_delete, sender=Comentario)
def excluir_arquivos_apos_commit(sender, instance, **kwargs):
    _agendar_exclusao_de_arquivos(instance)