import secrets

from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from .models import Hashtag


def hashtags_populares(request):
    total_posts = (
        Hashtag.objects.filter(pk=OuterRef("pk"))
        .annotate(total=Count("posts", distinct=True))
        .values("total")[:1]
    )
    total_comentarios = (
        Hashtag.objects.filter(pk=OuterRef("pk"))
        .annotate(total=Count("comentarios", distinct=True))
        .values("total")[:1]
    )
    return {
        "mutation_seed": secrets.token_hex(16),
        "hashtags_populares": (
            Hashtag.objects.annotate(
                total_posts=Coalesce(Subquery(total_posts), Value(0)),
                total_comentarios=Coalesce(Subquery(total_comentarios), Value(0)),
            )
            .annotate(total_usos=Value(0) + Subquery(total_posts) + Subquery(total_comentarios))
            .filter(total_usos__gt=0)
            .order_by("-total_usos", "nome")[:6]
        )
    }
