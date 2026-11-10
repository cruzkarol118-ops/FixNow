"""Pruebas del asistente orientador (chatbot)."""
from django.test import TestCase
from django.urls import reverse

from core.ia import predecir_categoria


class ChatbotOrientarTests(TestCase):
    def test_anonimo_obtiene_sugerencia_de_categoria(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "hay una fuga de agua bajo el lavaplatos"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["tipo"], "categoria")
        self.assertEqual(data["categoria"], "plomeria")

    def test_texto_corto_no_sugiere(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "hola"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["categoria"])

    def test_pregunta_de_producto_responde_faq(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "como funciona fixnow"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["tipo"], "producto")
        self.assertIn("técnico verificado", data["respuesta"])

    def test_texto_de_riesgo_no_clasifica(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "huele a gas en la cocina"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["tipo"], "riesgo")
        self.assertIsNone(data["categoria"])

    def test_riesgo_electrico_sugiere_categoria(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "el interruptor estaba saltando chispas"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["tipo"], "riesgo")
        self.assertEqual(data["categoria"], "electricidad")

    def test_json_invalido_devuelve_400(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data="no es json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_metodo_get_no_permitido(self):
        resp = self.client.get(reverse("chatbot_orientar"))
        self.assertEqual(resp.status_code, 405)

    def test_abstencion_cuando_clasificador_duda(self):
        # Texto sin señales claras: el clasificador debe abstenerse.
        cat, _ = predecir_categoria("buenas tardes gracias")
        self.assertIsNone(cat)

    def test_palabra_clave_sugiere_categoria_corta(self):
        # Texto corto con término claro: el chatbot respalda con palabras clave.
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "se rompio una tuberia"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["categoria"], "plomeria")

    def test_palabra_clave_tomacorriente(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "no enciende un tomacorriente"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["categoria"], "electricidad")

    def test_palabra_clave_llaves(self):
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "perdi las llaves de la puerta"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["categoria"], "cerrajeria")

    def test_texto_ambiguo_no_sugiere(self):
        # Menciona términos de dos categorías: no sugerir ninguna.
        resp = self.client.post(
            reverse("chatbot_orientar"),
            data={"texto": "se daño la nevera y hay una fuga de agua"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["categoria"])
