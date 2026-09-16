from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q

from krampt.paginacao import paginar
from posts.models import ImagemPost, Post, UsuarioBloqueado
from posts.services import posts_para_exibir

from .services import perfil_do


User = get_user_model()


def conteudo_do_perfil(usuario, visitante, aba, pagina):
    """Monta o read model das abas de um perfil."""
    pode_ver_salvos = usuario.pk == visitante.pk
    abas_validas = {"publicacoes", "repostados", "midia"}
    if pode_ver_salvos:
        abas_validas.add("salvos")
    if aba not in abas_validas:
        aba = "publicacoes"

    todos = Post.objects.filter(autor=usuario)
    totais = todos.aggregate(
        publicacoes=Count("pk", filter=Q(original__isnull=True)),
        repostados=Count("pk", filter=Q(original__isnull=False)),
        midia=Count(
            "pk",
            filter=Q(original__isnull=True) & ~Q(imagem=""),
        ),
    )

    total_salvos = (
        Post.objects.filter(
            salvos_por=visitante,
            original__isnull=True,
        ).count()
        if pode_ver_salvos
        else 0
    )

    if aba == "salvos":
        exibidos = Post.objects.filter(
            salvos_por=visitante,
            original__isnull=True,
        )
    elif aba == "repostados":
        exibidos = todos.filter(original__isnull=False)
    elif aba == "midia":
        exibidos = todos.filter(original__isnull=True).exclude(imagem="")
    else:
        exibidos = todos.filter(original__isnull=True)

    perfil = perfil_do(usuario)
    post_fixado = perfil.post_fixado if perfil else None

    if (
        post_fixado
        and post_fixado.autor_id == usuario.pk
        and aba == "publicacoes"
    ):
        exibidos = exibidos.exclude(pk=post_fixado.pk)

    pagina_objeto = paginar(
        exibidos.order_by("-criado_em", "-pk"),
        pagina,
    )
    posts = posts_para_exibir(
        pagina_objeto.object_list,
        visitante,
        incluir_comentarios=False,
    )

    post_fixado_exibicao = None
    if (
        post_fixado
        and post_fixado.autor_id == usuario.pk
        and aba == "publicacoes"
        and pagina_objeto.number == 1
    ):
        post_fixado_exibicao = posts_para_exibir(
            Post.objects.filter(pk=post_fixado.pk),
            visitante,
            incluir_comentarios=False,
        )[0]

    return {
        "aba": aba,
        "posts": posts,
        "post_fixado": post_fixado_exibicao,
        "pagina_objeto": pagina_objeto,
        "total_posts": totais["publicacoes"] + totais["repostados"],
        "total_publicacoes": totais["publicacoes"],
        "total_repostados": totais["repostados"],
        "total_midia": totais["midia"]
        + ImagemPost.objects.filter(
            post__autor=usuario,
            post__original__isnull=True,
        ).count(),
        "total_salvos": total_salvos,
        "pode_ver_salvos": pode_ver_salvos,
    }


def queryset_relacoes(usuario, tipo, visitante):
    """Query de seguidores/seguindo com estado de bloqueio anotado."""
    if tipo == "seguindo":
        perfil = perfil_do(usuario)
        queryset = (
            perfil.seguindo.all()
            if perfil
            else User.objects.none()
        )
    else:
        queryset = User.objects.filter(perfil__seguindo=usuario)

    bloqueio_direto = UsuarioBloqueado.objects.filter(
        usuario=visitante,
        bloqueado_id=OuterRef("pk"),
    )
    bloqueio_reverso = UsuarioBloqueado.objects.filter(
        usuario_id=OuterRef("pk"),
        bloqueado=visitante,
    )

    return (
        queryset.select_related("perfil")
        .annotate(
            bloqueado_com_visitante=(
                Exists(bloqueio_direto)
                | Exists(bloqueio_reverso)
            ),
        )
        .order_by("username", "pk")
    )
