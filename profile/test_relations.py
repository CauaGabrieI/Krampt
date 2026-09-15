from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from posts.models import UsuarioBloqueado

from .models import Perfil


class RelacoesPerfilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model()
        cls.dono = usuarios.objects.create_user(username="ana", first_name="Ana", password="senha-teste")
        cls.visitante = usuarios.objects.create_user(username="caua", first_name="Cauã", password="senha-teste")
        cls.seguido = usuarios.objects.create_user(username="bia", first_name="Bia", password="senha-teste")
        cls.seguidor = usuarios.objects.create_user(username="leo", first_name="Léo", password="senha-teste")
        cls.nao_relacionado = usuarios.objects.create_user(username="maria", password="senha-teste")

        cls.perfil_dono = Perfil.objects.create(usuario=cls.dono)
        cls.perfil_visitante = Perfil.objects.create(usuario=cls.visitante)
        cls.perfil_seguido = Perfil.objects.create(usuario=cls.seguido)
        cls.perfil_seguidor = Perfil.objects.create(usuario=cls.seguidor)
        Perfil.objects.create(usuario=cls.nao_relacionado)

        cls.perfil_dono.seguindo.add(cls.seguido)
        cls.perfil_seguidor.seguindo.add(cls.dono)

    def setUp(self):
        self.client.force_login(self.visitante)

    def test_contagens_sao_links_no_perfil_publico_e_no_proprio(self):
        publico = self.client.get(
            reverse("profile:perfil_publico", args=[self.dono.username])
        )
        self.assertContains(publico, reverse("profile:seguindo", args=[self.dono.username]))
        self.assertContains(publico, reverse("profile:seguidores", args=[self.dono.username]))

        proprio = self.client.get(reverse("profile:perfil"))
        self.assertContains(proprio, reverse("profile:seguindo", args=[self.visitante.username]))
        self.assertContains(proprio, reverse("profile:seguidores", args=[self.visitante.username]))

    def test_lista_seguindo_mostra_so_as_contas_seguidas(self):
        pagina = self.client.get(reverse("profile:seguindo", args=[self.dono.username]))

        self.assertEqual(pagina.status_code, 200)
        ids = [pessoa.pk for pessoa in pagina.context["pagina_objeto"].object_list]
        self.assertIn(self.seguido.pk, ids)
        self.assertNotIn(self.nao_relacionado.pk, ids)
        self.assertContains(
            pagina,
            reverse("profile:perfil_publico", args=[self.seguido.username]),
        )

    def test_lista_seguidores_mostra_so_os_seguidores(self):
        pagina = self.client.get(reverse("profile:seguidores", args=[self.dono.username]))

        self.assertEqual(pagina.status_code, 200)
        ids = [pessoa.pk for pessoa in pagina.context["pagina_objeto"].object_list]
        self.assertIn(self.seguidor.pk, ids)
        self.assertNotIn(self.nao_relacionado.pk, ids)

    def test_lista_de_relacoes_e_paginada_em_trinta(self):
        extras = []
        usuarios = get_user_model()
        for indice in range(31):
            usuario = usuarios.objects.create_user(
                username=f"extra{indice:02d}",
                password="senha-teste",
            )
            Perfil.objects.create(usuario=usuario)
            extras.append(usuario)
        self.perfil_dono.seguindo.add(*extras)

        primeira = self.client.get(reverse("profile:seguindo", args=[self.dono.username]))
        segunda = self.client.get(
            reverse("profile:seguindo", args=[self.dono.username]),
            {"page": 2},
        )

        self.assertEqual(len(primeira.context["pagina_objeto"].object_list), 30)
        self.assertTrue(primeira.context["pagina_objeto"].has_next())
        self.assertEqual(len(segunda.context["pagina_objeto"].object_list), 2)

    def test_bloqueio_nao_pode_ser_contornado_pela_url_da_lista(self):
        UsuarioBloqueado.objects.create(usuario=self.dono, bloqueado=self.visitante)

        pagina = self.client.get(reverse("profile:seguindo", args=[self.dono.username]))

        self.assertEqual(pagina.status_code, 200)
        self.assertTrue(pagina.context["bloqueado"])
        self.assertIsNone(pagina.context["pagina_objeto"])
        self.assertContains(pagina, "Perfil indisponível")

    def test_lista_nao_mostra_botao_de_seguir_para_si_mesmo(self):
        self.perfil_dono.seguindo.clear()
        self.perfil_dono.seguindo.add(self.visitante)

        pagina = self.client.get(reverse("profile:seguindo", args=[self.dono.username]))

        self.assertContains(pagina, "@caua")
        self.assertNotContains(
            pagina,
            reverse("profile:seguir", args=[self.visitante.pk]),
        )
