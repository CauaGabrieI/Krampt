from django.contrib.auth import get_user_model
from django.test import TestCase

from krampt.testing import QueryBudgetMixin
from posts.models import Post

from .models import Perfil
from .selectors import conteudo_do_perfil, queryset_relacoes


class PerfilSelectorsQueryBudgetTests(QueryBudgetMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.usuario = User.objects.create_user(
            username="budget_perfil"
        )
        cls.outro = User.objects.create_user(
            username="budget_perfil_outro"
        )
        perfil = Perfil.objects.create(usuario=cls.usuario)
        Perfil.objects.create(usuario=cls.outro)
        perfil.seguindo.add(cls.outro)

        for indice in range(30):
            Post.objects.create(
                autor=cls.usuario,
                conteudo=f"Perfil orçamento {indice}",
            )

    def test_conteudo_perfil_tem_orcamento_estavel(self):
        with self.assertMaxQueries(10):
            contexto = conteudo_do_perfil(
                self.usuario,
                self.usuario,
                "publicacoes",
                1,
            )

        self.assertEqual(len(contexto["posts"]), 20)
        self.assertEqual(contexto["total_publicacoes"], 30)

    def test_relacoes_nao_tem_n_mais_um(self):
        with self.assertMaxQueries(3):
            relacoes = list(
                queryset_relacoes(
                    self.usuario,
                    "seguindo",
                    self.usuario,
                )
            )

        self.assertEqual(
            [usuario.pk for usuario in relacoes],
            [self.outro.pk],
        )
