from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Post
from .services import filtrar_posts_visiveis, posts_para_exibir


User = get_user_model()


def queryset_feed(usuario, filtro_recebido):
    """Query de feed sem executar regra de escrita."""
    if filtro_recebido == "seguindo":
        # Faz o filtro pela relação no banco e evita materializar uma lista
        # intermediária de IDs de usuários seguidos.
        base = Post.objects.filter(autor__seguidores__usuario=usuario)
        filtro = "seguindo"
    else:
        base = Post.objects.all()
        filtro = ""

    return (
        filtrar_posts_visiveis(base, usuario).order_by("-criado_em", "-pk"),
        filtro,
    )


def buscar_pessoas(termo, usuario, limite=20):
    termo = (termo or "").strip()
    if not termo:
        return User.objects.none()

    return (
        User.objects.filter(
            Q(first_name__icontains=termo)
            | Q(username__icontains=termo)
        )
        .exclude(pk=usuario.pk)
        .select_related("perfil")
        .order_by("username")[:limite]
    )


def queryset_busca_posts(termo, usuario):
    termo = (termo or "").strip()
    if not termo:
        return Post.objects.none()

    return filtrar_posts_visiveis(
        Post.objects.filter(conteudo__icontains=termo),
        usuario,
    ).order_by("-criado_em", "-pk")


def preparar_posts(queryset, usuario, *, incluir_comentarios=False):
    """Read model de posts pronto para templates."""
    return posts_para_exibir(
        queryset,
        usuario,
        incluir_comentarios=incluir_comentarios,
    )
