from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from configuracoes.models import PreferenciasUsuario
from mensagens.context_processors import mensagens_nao_lidas
from mensagens.models import Conversa, Mensagem
from mensagens.services import AVISO_MENSAGEM_BLOQUEADA
from posts.models import UsuarioBloqueado
from profile.models import Perfil

User = get_user_model()


class CriarConversaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caua = User.objects.create_user(username="caua", password="senha")
        cls.maria = User.objects.create_user(username="maria", password="senha")

    def test_criar_conversa_exige_login(self):
        response = self.client.get(reverse("mensagens:nova"))

        self.assertEqual(response.status_code, 302)

    def test_lista_de_conversas_exige_login(self):
        response = self.client.get(reverse("mensagens:lista"))

        self.assertEqual(response.status_code, 302)

    def test_lista_mostra_estado_vazio(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("mensagens:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhuma conversa ainda")
        self.assertContains(response, "Comece uma conversa privada com quem você segue")
        self.assertContains(response, reverse("mensagens:nova"))
        self.assertContains(response, reverse("buscar"))
        self.assertEqual(response.context["total_conversas"], 0)

    def test_criar_conversa_redireciona_para_a_conversa_criada(self):
        self.client.force_login(self.caua)

        response = self.client.post(
            reverse("mensagens:nova"), {"usuario_id": self.maria.pk}
        )

        self.assertEqual(response.status_code, 302)
        conversa = (
            Conversa.objects.filter(participantes=self.caua)
            .filter(participantes=self.maria)
            .first()
        )
        self.assertIsNotNone(conversa)
        self.assertEqual(conversa.chave, f"{min(self.caua.pk, self.maria.pk)}:{max(self.caua.pk, self.maria.pk)}")
        self.assertRedirects(
            response, reverse("mensagens:detalhe", args=[conversa.pk])
        )

    def test_criar_conversa_reutiliza_a_existente(self):
        self.client.force_login(self.caua)
        conversa = Conversa.objects.create()
        conversa.participantes.add(self.caua, self.maria)

        response = self.client.post(
            reverse("mensagens:nova"), {"usuario_id": self.maria.pk}
        )

        self.assertEqual(
            Conversa.objects.filter(participantes=self.caua)
            .filter(participantes=self.maria)
            .count(),
            1,
        )
        self.assertRedirects(
            response, reverse("mensagens:detalhe", args=[conversa.pk])
        )

    def test_criar_conversa_com_usuario_inexistente_redireciona(self):
        self.client.force_login(self.caua)

        response = self.client.post(
            reverse("mensagens:nova"), {"usuario_id": 9999}
        )

        self.assertEqual(response.status_code, 404)

    def test_nao_cria_conversa_com_a_propria_conta(self):
        self.client.force_login(self.caua)

        response = self.client.post(
            reverse("mensagens:criar"), {"usuario_id": self.caua.pk}
        )

        self.assertRedirects(response, reverse("mensagens:lista"))
        self.assertFalse(Conversa.objects.exists())

    def test_bloqueio_impede_iniciar_conversa(self):
        UsuarioBloqueado.objects.create(usuario=self.maria, bloqueado=self.caua)
        self.client.force_login(self.caua)

        response = self.client.post(reverse("mensagens:criar"), {"usuario_id": self.maria.pk})

        self.assertRedirects(
            response,
            reverse("profile:perfil_publico", args=[self.maria.username]),
        )
        self.assertFalse(Conversa.objects.exists())

    def test_abrir_nova_conversa_nao_cria_perfil(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("mensagens:nova"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Perfil.objects.filter(usuario=self.caua).exists())


class ConversaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caua = User.objects.create_user(username="caua", password="senha")
        cls.maria = User.objects.create_user(username="maria", password="senha")
        cls.ricardo = User.objects.create_user(username="ricardo", password="senha")
        cls.conversa = Conversa.objects.create()
        cls.conversa.participantes.add(cls.caua, cls.maria)
        Mensagem.objects.create(
            conversa=cls.conversa, autor=cls.caua, conteudo="Oi, Maria!"
        )

    def test_so_quem_participa_acessa_a_conversa(self):
        self.client.force_login(self.ricardo)

        response = self.client.get(
            reverse("mensagens:detalhe", args=[self.conversa.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_aviso_no_header_conta_so_recebidas_nao_lidas(self):
        Mensagem.objects.create(conversa=self.conversa, autor=self.maria, conteudo="Nova")
        Mensagem.objects.create(conversa=self.conversa, autor=self.maria, conteudo="Já lida", lida=True)
        outra = Conversa.objects.create()
        outra.participantes.add(self.maria, self.ricardo)
        Mensagem.objects.create(conversa=outra, autor=self.maria, conteudo="Privada")
        self.client.force_login(self.caua)

        for url in [reverse("home"), reverse("mensagens:lista")]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.context["mensagens_nao_lidas"], 1)
                self.assertContains(response, 'aria-label="Mensagens (1 não lidas)"')
                self.assertContains(response, '<span class="header-messages-badge" aria-hidden="true">1</span>', html=True)

    def test_aviso_diminui_ao_ler_e_some_quando_nao_ha_pendencias(self):
        Mensagem.objects.create(conversa=self.conversa, autor=self.maria, conteudo="Nova")
        outra = Conversa.objects.create()
        outra.participantes.add(self.caua, self.ricardo)
        Mensagem.objects.create(conversa=outra, autor=self.ricardo, conteudo="Outra nova")
        self.client.force_login(self.caua)

        response = self.client.get(reverse("mensagens:lista"))
        self.assertEqual(response.context["mensagens_nao_lidas"], 2)
        response = self.client.get(reverse("mensagens:detalhe", args=[self.conversa.pk]))
        self.assertEqual(response.context["mensagens_nao_lidas"], 1)
        response = self.client.get(reverse("mensagens:detalhe", args=[outra.pk]))
        self.assertEqual(response.context["mensagens_nao_lidas"], 0)
        self.assertNotContains(response, 'class="header-messages-badge"')

    def test_contador_anonimo_nao_consulta_mensagens(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        with self.assertNumQueries(0):
            self.assertEqual(mensagens_nao_lidas(request), {})

    def test_envia_mensagem_e_exibe_a_conversa(self):
        self.client.force_login(self.caua)

        response = self.client.post(
            reverse("mensagens:detalhe", args=[self.conversa.pk]),
            {"conteudo": "Tudo bem?"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Mensagem.objects.filter(autor=self.caua, conteudo="Tudo bem?").exists()
        )

    def test_preferencia_atual_bloqueia_envio_em_conversa_existente(self):
        self.client.force_login(self.caua)
        url = reverse("mensagens:detalhe", args=[self.conversa.pk])
        self.client.post(url, {"conteudo": "Enviada antes da mudança"})
        self.assertTrue(Mensagem.objects.filter(conteudo="Enviada antes da mudança").exists())

        preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=self.maria)
        preferencias.permitir_novas_conversas = False
        preferencias.save(update_fields=["permitir_novas_conversas"])

        resposta = self.client.post(
            url,
            {"conteudo": "Não deve chegar"},
            follow=True,
        )

        self.assertFalse(Mensagem.objects.filter(conteudo="Não deve chegar").exists())
        self.assertContains(resposta, AVISO_MENSAGEM_BLOQUEADA)
        self.assertContains(resposta, 'class="global-toast global-toast--error"')
        self.assertNotContains(resposta, 'class="dm-composer"')
        self.assertContains(resposta, "Oi, Maria!")

    def test_bloqueio_atual_bloqueia_envio_em_conversa_existente(self):
        UsuarioBloqueado.objects.create(usuario=self.maria, bloqueado=self.caua)
        self.client.force_login(self.caua)

        resposta = self.client.post(
            reverse("mensagens:detalhe", args=[self.conversa.pk]),
            {"conteudo": "Mensagem bloqueada"},
            follow=True,
        )

        self.assertFalse(Mensagem.objects.filter(conteudo="Mensagem bloqueada").exists())
        self.assertContains(resposta, AVISO_MENSAGEM_BLOQUEADA)

    def test_permissao_seguindo_e_reavaliada_em_cada_envio(self):
        preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=self.maria)
        preferencias.mensagens_de = PreferenciasUsuario.PermissaoMensagem.SEGUINDO
        preferencias.save(update_fields=["mensagens_de"])
        self.client.force_login(self.caua)
        url = reverse("mensagens:detalhe", args=[self.conversa.pk])

        self.client.post(url, {"conteudo": "Bloqueada"})
        self.assertFalse(Mensagem.objects.filter(conteudo="Bloqueada").exists())

        perfil_maria, _ = Perfil.objects.get_or_create(usuario=self.maria)
        perfil_maria.seguindo.add(self.caua)
        self.client.post(url, {"conteudo": "Permitida"})
        self.assertTrue(Mensagem.objects.filter(autor=self.caua, conteudo="Permitida").exists())

        perfil_maria.seguindo.remove(self.caua)
        self.client.post(url, {"conteudo": "Bloqueada novamente"})
        self.assertFalse(Mensagem.objects.filter(conteudo="Bloqueada novamente").exists())

    def test_reabrir_permissao_libera_conversa_existente(self):
        preferencias, _ = PreferenciasUsuario.objects.get_or_create(usuario=self.maria)
        preferencias.permitir_novas_conversas = False
        preferencias.save(update_fields=["permitir_novas_conversas"])
        self.client.force_login(self.caua)
        url = reverse("mensagens:detalhe", args=[self.conversa.pk])

        self.client.post(url, {"conteudo": "Bloqueada"})
        preferencias.permitir_novas_conversas = True
        preferencias.mensagens_de = PreferenciasUsuario.PermissaoMensagem.TODOS
        preferencias.save(update_fields=["permitir_novas_conversas", "mensagens_de"])
        self.client.post(url, {"conteudo": "Liberada"})

        self.assertFalse(Mensagem.objects.filter(conteudo="Bloqueada").exists())
        self.assertTrue(Mensagem.objects.filter(autor=self.caua, conteudo="Liberada").exists())

    def test_mensagem_vazia_nao_e_enviada(self):
        self.client.force_login(self.caua)

        response = self.client.post(
            reverse("mensagens:detalhe", args=[self.conversa.pk]),
            {"conteudo": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório")
        self.assertFalse(Mensagem.objects.filter(conteudo="   ").exists())

    def test_mensagem_longa_mostra_erro_sem_salvar(self):
        self.client.force_login(self.caua)

        response = self.client.post(
            reverse("mensagens:detalhe", args=[self.conversa.pk]),
            {"conteudo": "x" * 281},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["formulario"].errors)
        self.assertEqual(self.conversa.mensagens.count(), 1)

    def test_nao_participante_nao_pode_enviar(self):
        self.client.force_login(self.ricardo)

        response = self.client.post(
            reverse("mensagens:detalhe", args=[self.conversa.pk]),
            {"conteudo": "Tentativa de acesso"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Mensagem.objects.filter(autor=self.ricardo).exists())

    def test_mensagens_ficam_lidas_ao_abrir_a_conversa(self):
        Mensagem.objects.create(
            conversa=self.conversa, autor=self.maria, conteudo="Oi!", lida=False
        )
        self.client.force_login(self.caua)

        self.client.get(reverse("mensagens:detalhe", args=[self.conversa.pk]))

        self.assertFalse(
            Mensagem.objects.filter(conversa=self.conversa, autor=self.maria, lida=False).exists()
        )

    def test_lista_ordena_pela_mensagem_mais_recente(self):
        outra = Conversa.objects.create()
        outra.participantes.add(self.caua, self.ricardo)
        Mensagem.objects.create(conversa=self.conversa, autor=self.maria, conteudo="Mensagem nova")
        self.client.force_login(self.caua)

        response = self.client.get(reverse("mensagens:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["conversas"][0]["conversa"], self.conversa)
        self.assertEqual(response.context["conversas"][1]["conversa"], outra)

    def test_lista_mostra_conversa_com_link_e_contador_de_nao_lidas(self):
        Mensagem.objects.create(conversa=self.conversa, autor=self.maria, conteudo="Nova mensagem")
        self.client.force_login(self.caua)

        response = self.client.get(reverse("mensagens:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("mensagens:detalhe", args=[self.conversa.pk]))
        self.assertContains(response, "@maria")
        self.assertContains(response, "Nova mensagem")
        self.assertContains(response, 'aria-label="1 não lidas"')
        self.assertEqual(response.context["total_conversas"], 1)
        self.assertEqual(response.context["total_nao_lidas"], 1)

    def test_filtro_mostra_apenas_conversas_com_nao_lidas(self):
        outra = Conversa.objects.create()
        outra.participantes.add(self.caua, self.ricardo)
        Mensagem.objects.create(conversa=outra, autor=self.caua, conteudo="Enviada por mim")
        Mensagem.objects.create(conversa=self.conversa, autor=self.maria, conteudo="Não lida")
        self.client.force_login(self.caua)

        response = self.client.get(reverse("mensagens:lista"), {"filtro": "nao_lidas"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["conversas"]), 1)
        self.assertEqual(response.context["conversas"][0]["conversa"], self.conversa)
        self.assertContains(response, "Não lida")

    def test_busca_filtra_por_usuario_e_mensagem(self):
        outra = Conversa.objects.create()
        outra.participantes.add(self.caua, self.ricardo)
        Mensagem.objects.create(conversa=outra, autor=self.ricardo, conteudo="Projeto secreto")
        self.client.force_login(self.caua)

        por_usuario = self.client.get(reverse("mensagens:lista"), {"q": "maria"})
        por_mensagem = self.client.get(reverse("mensagens:lista"), {"q": "secreto"})

        self.assertEqual(len(por_usuario.context["conversas"]), 1)
        self.assertEqual(por_usuario.context["conversas"][0]["conversa"], self.conversa)
        self.assertEqual(len(por_mensagem.context["conversas"]), 1)
        self.assertEqual(por_mensagem.context["conversas"][0]["conversa"], outra)

    def test_filtro_solicitacoes_nao_inventa_conversas(self):
        self.client.force_login(self.caua)

        response = self.client.get(reverse("mensagens:lista"), {"filtro": "solicitacoes"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filtro"], "solicitacoes")
        self.assertEqual(response.context["conversas"], [])
        self.assertContains(response, "Nenhuma solicitação")


class PaginacaoMensagensTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.caua = User.objects.create_user(username="caua", password="senha")
        cls.maria = User.objects.create_user(username="maria", password="senha")
        cls.conversa = Conversa.objects.create()
        cls.conversa.participantes.add(cls.caua, cls.maria)
        for i in range(31):
            Mensagem.objects.create(
                conversa=cls.conversa, autor=cls.maria, conteudo=f"Mensagem {i:02d}"
            )

    def test_conversa_pagina_em_trinta_e_mostra_mais_recentes_por_padrao(self):
        self.client.force_login(self.caua)

        pagina = self.client.get(reverse("mensagens:detalhe", args=[self.conversa.pk]))

        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.context["pagina_objeto"].number, 2)
        self.assertEqual(len(pagina.context["mensagens"]), 1)
        self.assertEqual(pagina.context["mensagens"][0].conteudo, "Mensagem 30")

        pagina_um = self.client.get(
            reverse("mensagens:detalhe", args=[self.conversa.pk]), {"page": 1}
        )

        self.assertEqual(len(pagina_um.context["mensagens"]), 30)
        self.assertContains(pagina_um, "Página 1 de 2")
