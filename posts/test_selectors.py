from django.contrib.auth import get_user_model
from django.test import TestCase

from krampt.paginacao import paginar
from krampt.testing import QueryBudgetMixin
from profile.models import Perfil

from .models import Post
from .selectors import preparar_posts, queryset_feed


class FeedSelectorsQueryBudgetTests(QueryBudgetMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.leitor = User.objects.create_user(
            username="budget_feed_leitor"
        )
        cls.autor = User.objects.create_user(
            username="budget_feed_autor"
        )
        perfil_leitor = Perfil.objects.create(usuario=cls.leitor)
        Perfil.objects.create(usuario=cls.autor)
        perfil_leitor.seguindo.add(cls.autor)

        for indice in range(35):
            Post.objects.create(
                autor=cls.autor,
                conteudo=f"Post de orçamento {indice}",
            )

    def test_feed_nao_cresce_queries_com_quantidade_de_posts(self):
        with self.assertMaxQueries(6):
            queryset, filtro = queryset_feed(
                self.leitor,
                "seguindo",
            )
            pagina = paginar(queryset, 1)
            posts = preparar_posts(
                pagina.object_list,
                self.leitor,
                incluir_comentarios=False,
            )

        self.assertEqual(filtro, "seguindo")
        self.assertEqual(len(posts), 20)
