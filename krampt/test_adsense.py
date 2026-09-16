from django.test import TestCase
from django.urls import reverse


class AdsenseVerificationTests(TestCase):
    def test_ads_txt_e_publico_e_tem_conteudo_exato(self):
        resposta = self.client.get(reverse("ads_txt"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.headers["Content-Type"],
            "text/plain; charset=utf-8",
        )
        self.assertEqual(
            resposta.content.decode(),
            "google.com, pub-9158694826036840, DIRECT, f08c47fec0942fa0\n",
        )

    def test_login_publico_expoe_metatag_adsense_no_head(self):
        resposta = self.client.get(reverse("login:login"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            '<meta name="google-adsense-account" '
            'content="ca-pub-9158694826036840">',
            html=True,
        )
