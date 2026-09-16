from dataclasses import dataclass

from django.db import transaction

from notificacoes.ports import PortaNotificacoes
from profile.models import Perfil

from .models import Comentario, ImagemPost, Post
from .ports import PortaProcessadorImagem
from .services import bloquear_usuarios_para_mutacao


@dataclass(frozen=True)
class ResultadoEstado:
    ativo: bool
    total: int | None = None


@dataclass(frozen=True)
class ResultadoFixacao:
    ativo: bool
    mensagem: str


@dataclass(frozen=True)
class ResultadoCriacao:
    objeto: object
    criado: bool
    duplicado: bool = False


def _estado_final(atual: bool, desejado: bool | None) -> bool:
    return (not atual) if desejado is None else desejado


class ServicoInteracoesPost:
    def __init__(self, notificacoes: PortaNotificacoes):
        self.notificacoes = notificacoes

    def curtir_post(self, usuario, post: Post, desejado: bool | None) -> ResultadoEstado:
        through = Post.curtidas.through
        with transaction.atomic():
            atual = through.objects.filter(
                post_id=post.pk,
                user_id=usuario.pk,
            ).exists()
            ativo = _estado_final(atual, desejado)

            if ativo:
                through.objects.get_or_create(
                    post_id=post.pk,
                    user_id=usuario.pk,
                )
                self.notificacoes.enviar(
                    post.autor,
                    "curtida",
                    usuario,
                    post=post,
                )
            else:
                through.objects.filter(
                    post_id=post.pk,
                    user_id=usuario.pk,
                ).delete()
                self.notificacoes.remover(
                    post.autor,
                    "curtida",
                    usuario,
                    post=post,
                )

            total = through.objects.filter(post_id=post.pk).count()
        return ResultadoEstado(ativo=ativo, total=total)

    def salvar_post(self, usuario, post: Post, desejado: bool | None) -> ResultadoEstado:
        with transaction.atomic():
            atual = post.salvos_por.filter(pk=usuario.pk).exists()
            ativo = _estado_final(atual, desejado)
            if ativo:
                post.salvos_por.add(usuario)
            else:
                post.salvos_por.remove(usuario)
        return ResultadoEstado(ativo=ativo)

    def republicar_post(self, usuario, post: Post, desejado: bool | None) -> ResultadoEstado:
        with transaction.atomic():
            atual = Post.objects.filter(
                autor=usuario,
                original=post,
            ).exists()
            ativo = _estado_final(atual, desejado)

            if ativo:
                Post.objects.get_or_create(
                    autor=usuario,
                    original=post,
                    defaults={"conteudo": ""},
                )
                self.notificacoes.enviar(
                    post.autor,
                    "repost",
                    usuario,
                    post=post,
                )
            else:
                Post.objects.filter(
                    autor=usuario,
                    original=post,
                ).delete()
                self.notificacoes.remover(
                    post.autor,
                    "repost",
                    usuario,
                    post=post,
                )

            total = Post.objects.filter(original=post).count()
        return ResultadoEstado(ativo=ativo, total=total)

    def curtir_comentario(
        self,
        usuario,
        comentario: Comentario,
        desejado: bool | None,
    ) -> ResultadoEstado:
        through = Comentario.curtidas.through
        with transaction.atomic():
            atual = through.objects.filter(
                comentario_id=comentario.pk,
                user_id=usuario.pk,
            ).exists()
            ativo = _estado_final(atual, desejado)

            if ativo:
                through.objects.get_or_create(
                    comentario_id=comentario.pk,
                    user_id=usuario.pk,
                )
                self.notificacoes.enviar(
                    comentario.autor,
                    "curtida_comentario",
                    usuario,
                    post=comentario.post,
                    comentario=comentario,
                )
            else:
                through.objects.filter(
                    comentario_id=comentario.pk,
                    user_id=usuario.pk,
                ).delete()
                self.notificacoes.remover(
                    comentario.autor,
                    "curtida_comentario",
                    usuario,
                    post=comentario.post,
                    comentario=comentario,
                )

            total = through.objects.filter(comentario_id=comentario.pk).count()
        return ResultadoEstado(ativo=ativo, total=total)

    def fixar_post(self, usuario, post: Post, desejado: bool | None) -> ResultadoFixacao:
        with transaction.atomic():
            perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
            perfil = Perfil.objects.select_for_update().get(pk=perfil.pk)

            atual = perfil.post_fixado_id == post.pk
            ativo = _estado_final(atual, desejado)

            if ativo:
                perfil.post_fixado = post
                mensagem = "Post fixado no perfil."
            elif atual:
                perfil.post_fixado = None
                mensagem = "Post desafixado."
            else:
                mensagem = "Post já estava desafixado."

            perfil.save(update_fields=["post_fixado"])
            ativo = perfil.post_fixado_id == post.pk

        return ResultadoFixacao(ativo=ativo, mensagem=mensagem)


class ServicoComandosPost:
    def __init__(
        self,
        notificacoes: PortaNotificacoes,
        processador_imagem: PortaProcessadorImagem,
    ):
        self.notificacoes = notificacoes
        self.processador_imagem = processador_imagem

    def criar_post(
        self,
        *,
        autor,
        conteudo: str,
        imagens,
        audio,
        chave_idempotencia: str | None,
    ) -> ResultadoCriacao:
        with transaction.atomic():
            if chave_idempotencia:
                bloquear_usuarios_para_mutacao(autor)
                existente = Post.objects.filter(
                    autor=autor,
                    original__isnull=True,
                    chave_idempotencia=chave_idempotencia,
                ).first()
                if existente is not None:
                    return ResultadoCriacao(
                        objeto=existente,
                        criado=False,
                        duplicado=True,
                    )

            post = Post.objects.create(
                autor=autor,
                conteudo=conteudo.strip(),
                imagem=(
                    self.processador_imagem.processar(imagens[0])
                    if imagens
                    else ""
                ),
                audio=audio or "",
                chave_idempotencia=chave_idempotencia,
            )
            for imagem in imagens[1:]:
                ImagemPost.objects.create(
                    post=post,
                    imagem=self.processador_imagem.processar(imagem),
                )

        return ResultadoCriacao(objeto=post, criado=True)

    def criar_comentario(
        self,
        *,
        autor,
        post: Post,
        dados: dict,
        chave_idempotencia: str | None,
    ) -> ResultadoCriacao:
        with transaction.atomic():
            existente = self._comentario_existente(autor, chave_idempotencia)
            if existente is not None:
                return ResultadoCriacao(
                    objeto=existente,
                    criado=False,
                    duplicado=True,
                )

            comentario = Comentario.objects.create(
                post=post,
                autor=autor,
                conteudo=dados["conteudo"],
                imagem=(
                    self.processador_imagem.processar(dados.get("imagem"))
                    if dados.get("imagem")
                    else ""
                ),
                audio=dados.get("audio") or "",
                chave_idempotencia=chave_idempotencia,
            )
            self.notificacoes.enviar(
                post.autor,
                "comentario",
                autor,
                post=post,
                comentario=comentario,
            )

        return ResultadoCriacao(objeto=comentario, criado=True)

    def responder_comentario(
        self,
        *,
        autor,
        comentario: Comentario,
        dados: dict,
        chave_idempotencia: str | None,
    ) -> ResultadoCriacao:
        with transaction.atomic():
            existente = self._comentario_existente(autor, chave_idempotencia)
            if existente is not None:
                return ResultadoCriacao(
                    objeto=existente,
                    criado=False,
                    duplicado=True,
                )

            resposta = Comentario.objects.create(
                post=comentario.post,
                autor=autor,
                resposta_para=comentario.resposta_para or comentario,
                conteudo=dados["conteudo"],
                imagem=(
                    self.processador_imagem.processar(dados.get("imagem"))
                    if dados.get("imagem")
                    else ""
                ),
                audio=dados.get("audio") or "",
                chave_idempotencia=chave_idempotencia,
            )
            self.notificacoes.enviar(
                comentario.autor,
                "resposta",
                autor,
                post=comentario.post,
                comentario=resposta,
            )

        return ResultadoCriacao(objeto=resposta, criado=True)

    @staticmethod
    def _comentario_existente(autor, chave_idempotencia):
        if not chave_idempotencia:
            return None
        bloquear_usuarios_para_mutacao(autor)
        return Comentario.objects.filter(
            autor=autor,
            chave_idempotencia=chave_idempotencia,
        ).first()
