"""
Suite de los 132 casos de prueba de casos_de_prueba_fixnow.md.

Cada test corresponde 1:1 a un caso de prueba (CP-FN1-01 ... IA-04) y su
nombre sigue el patrón test_cp_<bloque>_<numero>_<slug> para poder rastrearlo
contra el documento. Ejecución:

    .venv\\Scripts\\python.exe manage.py test core.tests_casos_prueba
"""
import tempfile
from datetime import date, datetime, timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Calificacion, Comision, DocumentoTecnico, IASugerencia, Notificacion,
    Pago, PerfilTecnico, Solicitud, Usuario,
)


def _certificado(nombre="cert.pdf", contenido=None):
    if contenido is None:
        contenido = b"%PDF-1.4\n1 0 obj\nendobj\ntrailer\n"
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


def _foto(nombre="foto.jpg", formato="JPEG"):
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (10, 10), (200, 30, 30)).save(buffer, format=formato)
    tipo = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif"}[formato]
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type=tipo)


def _foto_pesada():
    """Foto jpg válida (Pillow la abre) pero de más de 5 MB."""
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="JPEG")
    contenido = buffer.getvalue() + b"\0" * (6 * 1024 * 1024)
    return SimpleUploadedFile("foto_pesada.jpg", contenido, content_type="image/jpeg")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="fixnow-cp-media-"))
class _Base(TestCase):
    """Fábrica compartida: usuarios con datos válidos y únicos por test."""

    n = 0

    def _usuario(self, rol, correo, estado=Usuario.Estado.ACTIVO,
                 password="Clave123!", staff=False, **extra):
        type(self).n += 1
        n = type(self).n
        iniciales = (chr(65 + n % 26) + chr(65 + (n // 26) % 26)
                     + chr(65 + (n // 676) % 26))
        datos = {
            "cedula": f"{70000000 + n}",
            "nombre_completo": f"Usuario Prueba {iniciales}",
            "telefono": "3001234567",
            "rol": rol,
            "estado": estado,
            "direccion": "Cra 13 #52-40",
            "is_staff": staff,
            "is_superuser": staff,
        }
        datos.update(extra)
        return Usuario.objects.create_user(correo=correo, password=password, **datos)

    def _cliente(self, correo="cliente@test.co", **kw):
        return self._usuario(Usuario.Rol.CLIENTE, correo, **kw)

    def _tecnico(self, correo="tecnico@test.co", especialidad="plomeria",
                 disponible=True, estado=Usuario.Estado.ACTIVO,
                 precio_referencia=None, lat=None, lng=None, **kw):
        usuario = self._usuario(Usuario.Rol.TECNICO, correo, estado=estado, **kw)
        if lat is not None:
            usuario.latitud, usuario.longitud = lat, lng
            usuario.save(update_fields=["latitud", "longitud"])
        PerfilTecnico.objects.create(
            usuario=usuario, especialidad=especialidad, ciudad="Bogotá",
            documento_certificacion=_certificado(f"cert-{correo}.pdf"),
            disponible=disponible, precio_referencia=precio_referencia,
        )
        return usuario

    def _admin(self, correo=None):
        if correo is None:
            type(self).n += 1
            correo = f"admin{type(self).n}@test.co"
        return self._usuario(Usuario.Rol.ADMINISTRADOR, correo, staff=True)

    def _solicitud(self, cliente, categoria="plomeria",
                   descripcion="Fuga de agua bajo el lavaplatos.",
                   estado=Solicitud.Estado.PENDIENTE, tecnico=None,
                   precio_ofrecido=None, visible_tecnicos=True):
        return Solicitud.objects.create(
            cliente=cliente, categoria=categoria, descripcion=descripcion,
            direccion="Cra 13 #52-40", urgencia=Solicitud.Urgencia.NORMAL,
            estado=estado, tecnico=tecnico, precio_ofrecido=precio_ofrecido,
            visible_tecnicos=visible_tecnicos,
        )

    def _finalizar(self, solicitud, monto=10000):
        solicitud.finalizar(notas="Trabajo listo.", monto_final=monto)
        return solicitud

    def _calificacion(self, solicitud, estrellas, comentario=""):
        return Calificacion.objects.create(
            solicitud=solicitud, estrellas=estrellas, comentario=comentario)

    def _registro_cliente(self, **cambios):
        type(self).n += 1
        n = type(self).n
        datos = {
            "cedula": f"1098{n:06d}",
            "nombre_completo": "Cliente Nuevo Prueba",
            "correo": f"nuevo{n}@test.co",
            "telefono": "3001234567",
            "password": "Clave123!",
            "password2": "Clave123!",
            "terminos": "on",
        }
        datos.update(cambios)
        return self.client.post(reverse("registro_cliente"), datos)

    def _registro_tecnico(self, **cambios):
        type(self).n += 1
        n = type(self).n
        datos = {
            "cedula": f"2085{n:06d}",
            "nombre_completo": "Tecnico Nuevo Prueba",
            "correo": f"tecnuevo{n}@test.co",
            "telefono": "3001234567",
            "especialidad": "plomeria",
            "ciudad": "Bogotá",
            "documento_certificacion": _certificado(f"cert{n}.pdf"),
            "password": "Clave123!",
            "password2": "Clave123!",
            "terminos": "on",
        }
        datos.update(cambios)
        return self.client.post(reverse("registro_tecnico"), datos)

    def _post_perfil_cliente(self, cli, **cambios):
        datos = {
            "nombre_completo": "Cliente Editado Prueba",
            "telefono": "3111111111",
            "direccion": "Cl 63 #9-15",
            "fecha_nacimiento": "1990-05-10",
        }
        datos.update(cambios)
        return self.client.post(reverse("cliente_perfil"), datos)

    def _post_perfil_tecnico(self, tec, **cambios):
        perfil = tec.perfil_tecnico
        datos = {
            "nombre_completo": "Tecnico Editado Prueba",
            "telefono": "3111111111",
            "especialidad": perfil.especialidad,
            "ciudad": perfil.ciudad,
            "zona_cobertura": "Norte de Bogotá",
        }
        datos.update(cambios)
        return self.client.post(reverse("tecnico_perfil"), datos)


# =====================================================================
# FN-1: Registro de cliente (18 casos)
# =====================================================================
class TestFN1RegistroCliente(_Base):

    def test_cp_fn1_01_registro_valido_crea_cliente_activo(self):
        resp = self._registro_cliente(correo="nuevo@test.co", cedula="1098765432")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Usuario.objects.filter(correo="nuevo@test.co").exists())
        usuario = Usuario.objects.get(correo="nuevo@test.co")
        self.assertEqual(usuario.rol, Usuario.Rol.CLIENTE)
        self.assertEqual(usuario.estado, Usuario.Estado.ACTIVO)

    def test_cp_fn1_02_cedula_valida_6_y_10_digitos(self):
        for cedula in ("123456", "1234567890"):
            resp = self._registro_cliente(cedula=cedula, correo=f"{cedula}@test.co")
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(Usuario.objects.filter(cedula=cedula).exists())

    def test_cp_fn1_03_cedula_corta_o_larga_rechazada(self):
        for cedula in ("12345", "12345678901"):
            resp = self._registro_cliente(cedula=cedula, correo=f"{cedula}@test.co")
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(Usuario.objects.filter(correo=f"{cedula}@test.co").exists())

    def test_cp_fn1_04_cedula_con_letras_o_guiones_rechazada(self):
        for cedula in ("12345A", "12345-678", "1234 5678"):
            resp = self._registro_cliente(cedula=cedula, correo=f"{cedula}@test.co")
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(Usuario.objects.filter(correo=f"{cedula}@test.co").exists())

    def test_cp_fn1_05_cedula_duplicada_rechazada(self):
        existente = self._cliente(cedula="1098765432")
        resp = self._registro_cliente(cedula="1098765432", correo="otro@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "con esta cédula")
        self.assertFalse(Usuario.objects.filter(correo="otro@test.co").exists())
        self.assertEqual(Usuario.objects.filter(cedula="1098765432").count(), 1)
        self.assertEqual(Usuario.objects.get(cedula="1098765432").pk, existente.pk)

    def test_cp_fn1_06_nombre_en_limites_3_y_100(self):
        resp = self._registro_cliente(nombre_completo="Ana", correo="ana@test.co")
        self.assertEqual(resp.status_code, 302)
        resp = self._registro_cliente(nombre_completo="A" * 100, correo="largo@test.co")
        self.assertEqual(resp.status_code, 302)
        resp = self._registro_cliente(nombre_completo="Li", correo="corto@test.co")
        self.assertEqual(resp.status_code, 200)
        resp = self._registro_cliente(nombre_completo="A" * 101, correo="x101@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="corto@test.co").exists())
        self.assertFalse(Usuario.objects.filter(correo="x101@test.co").exists())

    def test_cp_fn1_07_nombre_con_tildes_ene_valido_y_digitos_invalidos(self):
        resp = self._registro_cliente(
            nombre_completo="María Pérez Ñoñez", correo="maria@test.co")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Usuario.objects.filter(correo="maria@test.co").exists())
        resp = self._registro_cliente(nombre_completo="Juan123!", correo="juan@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="juan@test.co").exists())

    def test_cp_fn1_08_correos_mal_formados_rechazados(self):
        for correo in ("sinarroba", "usuario@", "@dominio.com", "usuario@.com",
                       "con espacio@test.co"):
            resp = self._registro_cliente(correo=correo)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(Usuario.objects.filter(correo=correo).exists())

    def test_cp_fn1_09_correo_duplicado_rechazado(self):
        self._cliente(correo="yaexiste@test.co")
        resp = self._registro_cliente(correo="yaexiste@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "con este correo")

    def test_cp_fn1_10_telefono_valido_7_a_15_y_letras_rechazadas(self):
        resp = self._registro_cliente(telefono="3001234", correo="t7@test.co")
        self.assertEqual(resp.status_code, 302)
        resp = self._registro_cliente(
            telefono="300123456789012", correo="t15@test.co")
        self.assertEqual(resp.status_code, 302)
        resp = self._registro_cliente(telefono="300123", correo="t6@test.co")
        self.assertEqual(resp.status_code, 200)
        resp = self._registro_cliente(
            telefono="3001234567890123", correo="t16@test.co")
        self.assertEqual(resp.status_code, 200)
        resp = self._registro_cliente(telefono="300ABC4567", correo="tletras@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="tletras@test.co").exists())

    def test_cp_fn1_11_formulario_muestra_checklist_de_password(self):
        resp = self.client.get(reverse("registro_cliente"))
        self.assertContains(resp, "Mínimo 8 caracteres")
        self.assertContains(resp, "Una mayúscula")
        self.assertContains(resp, "Un número")
        self.assertContains(resp, "Un símbolo")

    def test_cp_fn1_12_password_cumple_politica(self):
        resp = self._registro_cliente(
            correo="politica@test.co", password="A1b2c3d4!", password2="A1b2c3d4!")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Usuario.objects.filter(correo="politica@test.co").exists())

    def test_cp_fn1_13_passwords_diferentes_rechazados(self):
        resp = self._registro_cliente(password2="OtraClave9!")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "no coinciden")

    def test_cp_fn1_14_sin_terminos_rechazado(self):
        datos_sin_terminos = {
            "cedula": "1098765001", "nombre_completo": "Cliente Sin Terminos",
            "correo": "sinterminos@test.co", "telefono": "3001234567",
            "password": "Clave123!", "password2": "Clave123!",
        }
        resp = self.client.post(reverse("registro_cliente"), datos_sin_terminos)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Debes aceptar los términos")
        self.assertFalse(
            Usuario.objects.filter(correo="sinterminos@test.co").exists())

    def test_cp_fn1_15_campos_obligatorios_marcan_error(self):
        resp = self.client.post(reverse("registro_cliente"), {})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "obligatorio")

    def test_cp_fn1_16_registro_autentica_y_relogin_funciona(self):
        self._registro_cliente(correo="relogin@test.co", cedula="1098765433")
        self.client.get(reverse("logout"))
        resp = self.client.post(reverse("login"), {
            "correo": "relogin@test.co", "clave": "Clave123!"})
        self.assertEqual(resp.status_code, 302)

    def test_cp_fn1_17_password_se_guarda_hasheada(self):
        self._registro_cliente(correo="hash@test.co", cedula="1098765434")
        usuario = Usuario.objects.get(correo="hash@test.co")
        self.assertNotEqual(usuario.password, "Clave123!")
        self.assertIn("$", usuario.password)
        self.assertTrue(usuario.check_password("Clave123!"))

    def test_cp_fn1_18_formulario_tiene_enlaces_a_tecnico_y_login(self):
        resp = self.client.get(reverse("registro_cliente"))
        self.assertContains(resp, "/registro/tecnico/")
        self.assertContains(resp, "/ingresar/")


# =====================================================================
# FN-2: Edición de perfil del cliente (16 casos)
# =====================================================================
class TestFN2EditarPerfilCliente(_Base):

    def test_cp_fn2_01_guarda_nombre_telefono_direccion_y_fecha(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli)
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.nombre_completo, "Cliente Editado Prueba")
        self.assertEqual(cli.telefono, "3111111111")
        self.assertEqual(cli.direccion, "Cl 63 #9-15")
        self.assertEqual(cli.fecha_nacimiento, date(1990, 5, 10))

    def test_cp_fn2_02_nombre_minimo_3_caracteres_aceptado(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, nombre_completo="Ana")
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.nombre_completo, "Ana")

    def test_cp_fn2_03_nombre_de_2_caracteres_rechazado(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, nombre_completo="Li")
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertNotEqual(cli.nombre_completo, "Li")

    def test_cp_fn2_04_nombre_de_100_caracteres_aceptado(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, nombre_completo="A" * 100)
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.nombre_completo, "A" * 100)

    def test_cp_fn2_05_nombre_de_101_caracteres_rechazado(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, nombre_completo="A" * 101)
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertNotEqual(cli.nombre_completo, "A" * 101)

    def test_cp_fn2_06_nombre_acepta_tildes_y_rechaza_digitos(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, nombre_completo="Juan123!")
        self.assertEqual(resp.status_code, 200)
        resp = self._post_perfil_cliente(cli, nombre_completo="María Pérez Ñoñez")
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.nombre_completo, "María Pérez Ñoñez")

    def test_cp_fn2_07_telefono_valido_7_a_15_digitos(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, telefono="3001234")
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.telefono, "3001234")
        resp = self._post_perfil_cliente(cli, telefono="300123456789012")
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.telefono, "300123456789012")
        resp = self._post_perfil_cliente(cli, telefono="300123")
        self.assertEqual(resp.status_code, 200)
        resp = self._post_perfil_cliente(cli, telefono="3001234567890123")
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertEqual(cli.telefono, "300123456789012")

    def test_cp_fn2_08_telefono_con_letras_rechazado(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, telefono="300ABC4567")
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertNotEqual(cli.telefono, "300ABC4567")

    def test_cp_fn2_09_direccion_vacia_rechazada(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, direccion="")
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertEqual(cli.direccion, "Cra 13 #52-40")

    def test_cp_fn2_10_fecha_nacimiento_futura_rechazada(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, fecha_nacimiento="2030-01-01")
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertIsNone(cli.fecha_nacimiento)

    def test_cp_fn2_11_cedula_no_es_editable(self):
        cli = self._cliente(cedula="1098765432")
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, cedula="1111111111")
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.cedula, "1098765432")

    def test_cp_fn2_12_cambio_de_correo_exige_codigo_y_password(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, correo_nuevo="nuevo@test.co")
        self.assertEqual(resp.status_code, 302)
        pendiente = self.client.session.get("cambio_correo")
        self.assertIsNotNone(pendiente)
        self.assertEqual(pendiente["correo"], "nuevo@test.co")
        cli.refresh_from_db()
        self.assertEqual(cli.correo, "cliente@test.co")
        resp = self.client.get(reverse("cliente_perfil"))
        self.assertContains(resp, pendiente["codigo"])
        resp = self.client.post(reverse("cliente_perfil"), {
            "confirmar_correo": "1",
            "codigo": pendiente["codigo"],
            "password": "Clave123!",
        })
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.correo, "nuevo@test.co")
        self.assertIsNone(self.client.session.get("cambio_correo"))

    def test_cp_fn2_13_correo_nuevo_que_ya_existe_rechazado(self):
        cli = self._cliente()
        otro = self._cliente(correo="otro@test.co")
        self.client.force_login(cli)
        resp = self._post_perfil_cliente(cli, correo_nuevo=otro.correo)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ya existe una cuenta registrada con este correo.")
        self.assertIsNone(self.client.session.get("cambio_correo"))
        cli.refresh_from_db()
        self.assertEqual(cli.correo, "cliente@test.co")

    def test_cp_fn2_14_cambio_password_exige_la_actual(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.post(reverse("cambiar_password"), {
            "old_password": "Mala999!",
            "new_password1": "NuevaClave1!",
            "new_password2": "NuevaClave1!",
        })
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertFalse(cli.check_password("NuevaClave1!"))
        resp = self.client.post(reverse("cambiar_password"), {
            "old_password": "Clave123!",
            "new_password1": "NuevaClave1!",
            "new_password2": "NuevaClave1!",
        })
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertTrue(cli.check_password("NuevaClave1!"))

    def test_cp_fn2_15_nueva_password_debe_cumplir_politica(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.post(reverse("cambiar_password"), {
            "old_password": "Clave123!",
            "new_password1": "corta",
            "new_password2": "corta",
        })
        self.assertEqual(resp.status_code, 200)
        cli.refresh_from_db()
        self.assertFalse(cli.check_password("corta"))
        self.assertTrue(cli.check_password("Clave123!"))

    def test_cp_fn2_16_cliente_suspendido_no_edita_su_perfil(self):
        cli = self._cliente()
        cli.suspender("prueba QA")
        self.client.force_login(cli)
        resp = self.client.get(reverse("cliente_perfil"))
        self.assertEqual(resp.status_code, 302)


# =====================================================================
# FN-4: Técnicos disponibles (12 casos)
# =====================================================================
class TestFN4TecnicosDisponibles(_Base):

    def _escenario(self):
        cli = self._cliente(correo="cli@test.co", latitud=4.65, longitud=-74.05)
        a = self._tecnico(correo="a@test.co", especialidad="plomeria",
                          disponible=True, precio_referencia=60000,
                          lat=4.651, lng=-74.06)
        b = self._tecnico(correo="b@test.co", especialidad="plomeria",
                          disponible=True, precio_referencia=None,
                          lat=4.72, lng=-74.12)
        c = self._tecnico(correo="c@test.co", especialidad="electricidad",
                          disponible=True, precio_referencia=50000,
                          lat=4.652, lng=-74.06)
        d = self._tecnico(correo="d@test.co", especialidad="plomeria",
                          disponible=False, lat=4.653, lng=-74.06)
        e = self._tecnico(correo="e@test.co", especialidad="plomeria",
                          disponible=True, estado=Usuario.Estado.SUSPENDIDO,
                          lat=4.654, lng=-74.06)
        sol = self._solicitud(cli)
        self.client.force_login(cli)
        return cli, a, b, c, d, e, sol

    def test_cp_fn4_01_lista_solo_disponibles_de_su_categoria(self):
        cli, a, b, c, d, e, sol = self._escenario()
        resp = self.client.get(reverse("tecnicos"))
        self.assertEqual(resp.status_code, 200)
        nombres = [t["nombre"] for t in resp.context["tecnicos"]]
        self.assertIn(a.nombre_completo, nombres)
        self.assertIn(b.nombre_completo, nombres)
        self.assertNotIn(c.nombre_completo, nombres)
        self.assertNotIn(d.nombre_completo, nombres)
        self.assertNotIn(e.nombre_completo, nombres)

    def test_cp_fn4_02_tarjeta_muestra_rating_precio_y_distancia(self):
        cli, a, b, c, d, e, sol = self._escenario()
        perfil = a.perfil_tecnico
        perfil.calificacion_promedio = 4.5
        perfil.total_calificaciones = 3
        perfil.save(update_fields=["calificacion_promedio", "total_calificaciones"])
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, "4,5")
        self.assertContains(resp, "$60.000")
        self.assertContains(resp, " km")

    def test_cp_fn4_03_tecnico_sin_calificaciones_muestra_placeholder(self):
        cli, a, b, c, d, e, sol = self._escenario()
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, "Sin calificaciones")
        nombres = [t["nombre"] for t in resp.context["tecnicos"]]
        self.assertIn(b.nombre_completo, nombres)

    def test_cp_fn4_04_sin_precio_muestra_a_convenir(self):
        cli, a, b, c, d, e, sol = self._escenario()
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, "a convenir")

    def test_cp_fn4_05_interfaz_tiene_selector_de_orden(self):
        cli, a, b, c, d, e, sol = self._escenario()
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, 'data-orden="calificacion"')
        self.assertContains(resp, 'id="filtroOrden"')
        self.assertContains(resp, "aplicar()")

    def test_cp_fn4_06_interfaz_tiene_radios_y_ampliacion(self):
        cli, a, b, c, d, e, sol = self._escenario()
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, 'data-radio="2"')
        self.assertContains(resp, 'data-radio="10"')
        self.assertContains(resp, "No hay técnicos dentro de este radio")
        self.assertContains(resp, 'id="ampliar"')

    def test_cp_fn4_07_disponibilidad_inactiva_lo_excluye(self):
        cli, a, b, c, d, e, sol = self._escenario()
        resp = self.client.get(reverse("tecnicos"))
        nombres = [t["nombre"] for t in resp.context["tecnicos"]]
        self.assertNotIn(d.nombre_completo, nombres)

    def test_cp_fn4_08_otra_categoria_no_aparece_con_pendiente(self):
        cli, a, b, c, d, e, sol = self._escenario()
        resp = self.client.get(reverse("tecnicos"))
        nombres = [t["nombre"] for t in resp.context["tecnicos"]]
        self.assertNotIn(c.nombre_completo, nombres)

    def test_cp_fn4_09_sin_tecnicos_muestra_mensaje(self):
        cli, a, b, c, d, e, sol = self._escenario()
        PerfilTecnico.objects.all().delete()
        Usuario.objects.filter(rol=Usuario.Rol.TECNICO).delete()
        resp = self.client.get(reverse("tecnicos"))
        self.assertEqual(resp.context["tecnicos"], [])
        self.assertContains(resp, "No hay técnicos dentro de este radio")

    def test_cp_fn4_10_cliente_sin_ubicacion_usa_fallback(self):
        cli, a, b, c, d, e, sol = self._escenario()
        cli2 = self._cliente(correo="cli2@test.co", latitud=None, longitud=None)
        self._solicitud(cli2)
        self.client.force_login(cli2)
        resp = self.client.get(reverse("tecnicos"))
        self.assertTrue(resp.context["mapa_fallback"])
        self.assertContains(resp, "usamos la dirección de tu perfil")

    def test_cp_fn4_11_sin_pendientes_muestra_todas_las_categorias(self):
        cli, a, b, c, d, e, sol = self._escenario()
        cli2 = self._cliente(correo="cli2@test.co")
        self.client.force_login(cli2)
        resp = self.client.get(reverse("tecnicos"))
        nombres = [t["nombre"] for t in resp.context["tecnicos"]]
        self.assertIn(c.nombre_completo, nombres)
        self.assertContains(resp, "Sin solicitud pendiente")

    def test_cp_fn4_12_elegir_dirige_la_solicitud_al_tecnico(self):
        cli, a, b, c, d, e, sol = self._escenario()
        url = f"{reverse('tecnicos')}?solicitud={sol.pk}&elegir={a.pk}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.tecnico, a)
        self.assertEqual(sol.estado, Solicitud.Estado.PENDIENTE)
        self.client.force_login(a)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertContains(resp, sol.descripcion)


# =====================================================================
# FN-8: Registro de técnico (14 casos)
# =====================================================================
class TestFN8RegistroTecnico(_Base):

    def test_cp_fn8_01_registro_valido_queda_pendiente(self):
        resp = self._registro_tecnico(
            correo="tecnuevo@test.co", cedula="2085765432")
        self.assertEqual(resp.status_code, 200)
        usuario = Usuario.objects.get(correo="tecnuevo@test.co")
        self.assertEqual(usuario.rol, Usuario.Rol.TECNICO)
        self.assertEqual(usuario.estado, Usuario.Estado.PENDIENTE_APROBACION)
        self.assertTrue(PerfilTecnico.objects.filter(usuario=usuario).exists())

    def test_cp_fn8_02_pendiente_no_puede_entrar(self):
        tec = self._tecnico(correo="pend@test.co", estado=Usuario.Estado.PENDIENTE_APROBACION,
                            disponible=False)
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertEqual(resp.status_code, 302)
        self.client.get(reverse("logout"))
        resp = self.client.post(reverse("login"), {
            "correo": tec.correo, "clave": "Clave123!"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "pendiente de aprobación")

    def test_cp_fn8_03_cedula_y_correo_duplicados_rechazados(self):
        cli = self._cliente(cedula="1098765432", correo="cli@test.co")
        resp = self._registro_tecnico(cedula="1098765432", correo="tecnuevo@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "con esta cédula")
        self.assertFalse(
            Usuario.objects.filter(correo="tecnuevo@test.co").exists())
        resp = self._registro_tecnico(cedula="2085765431", correo="cli@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "con este correo")

    def test_cp_fn8_04_especialidad_obligatoria(self):
        resp = self._registro_tecnico(especialidad="")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            Usuario.objects.filter(
                correo__startswith="tecnuevo", rol=Usuario.Rol.TECNICO).exists())

    def test_cp_fn8_05_ciudad_obligatoria(self):
        resp = self._registro_tecnico(ciudad="")
        self.assertEqual(resp.status_code, 200)

    def test_cp_fn8_06_certificacion_obligatoria(self):
        datos = {
            "cedula": "2085765001", "nombre_completo": "Tecnico Sin Doc",
            "correo": "sindoc@test.co", "telefono": "3001234567",
            "especialidad": "plomeria", "ciudad": "Bogotá",
            "password": "Clave123!", "password2": "Clave123!",
            "terminos": "on",
        }
        resp = self.client.post(reverse("registro_tecnico"), datos)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Adjunta tu certificación")

    def test_cp_fn8_07_acepta_pdf_y_png(self):
        resp = self._registro_tecnico(correo="condoc@test.co", cedula="2085765401")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Usuario.objects.filter(correo="condoc@test.co").exists())
        png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
               b"\x00\x00\x00\x01\x08\x02\x00\x00\x00")
        resp = self._registro_tecnico(
            correo="conpng@test.co", cedula="2085765402",
            documento_certificacion=_certificado("cert.png", png))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Usuario.objects.filter(correo="conpng@test.co").exists())

    def test_cp_fn8_08_rechaza_formato_invalido_y_mas_de_5mb(self):
        resp = self._registro_tecnico(
            correo="condoc@test.co",
            documento_certificacion=_certificado("cert.doc"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="condoc@test.co").exists())
        pesado = b"%PDF-1.4" + b"\0" * (6 * 1024 * 1024)
        resp = self._registro_tecnico(
            correo="conpesado@test.co",
            documento_certificacion=_certificado("certbig.pdf", pesado))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            Usuario.objects.filter(correo="conpesado@test.co").exists())

    def test_cp_fn8_09_valida_cedula_nombre_y_telefono(self):
        resp = self._registro_tecnico(cedula="12345", correo="c1@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="c1@test.co").exists())
        resp = self._registro_tecnico(
            nombre_completo="Ju", correo="c2@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="c2@test.co").exists())
        resp = self._registro_tecnico(telefono="300ABC4567", correo="c3@test.co")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="c3@test.co").exists())

    def test_cp_fn8_10_politica_de_password_y_coincidencia(self):
        resp = self._registro_tecnico(
            correo="p1@test.co", password="clave123!", password2="clave123!")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="p1@test.co").exists())
        resp = self._registro_tecnico(
            correo="p2@test.co", password2="OtraClave9!")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(correo="p2@test.co").exists())

    def test_cp_fn8_11_sin_terminos_rechazado(self):
        resp = self._registro_tecnico(terminos="")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Debes aceptar los términos")

    def test_cp_fn8_12_nuevo_tecnico_arranca_no_disponible(self):
        self._registro_tecnico(correo="nodisp@test.co", cedula="2085765403")
        usuario = Usuario.objects.get(correo="nodisp@test.co")
        self.assertFalse(usuario.perfil_tecnico.disponible)

    def test_cp_fn8_13_no_puede_autoproclamarse_administrador(self):
        resp = self._registro_tecnico(
            correo="malicioso@test.co", rol="administrador", is_staff="on")
        self.assertEqual(resp.status_code, 200)
        usuario = Usuario.objects.get(correo="malicioso@test.co")
        self.assertEqual(usuario.rol, Usuario.Rol.TECNICO)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_cp_fn8_14_formulario_enlaza_al_registro_de_cliente(self):
        resp = self.client.get(reverse("registro_tecnico"))
        self.assertContains(resp, "Crea tu cuenta de cliente")


# =====================================================================
# FN-9: Edición de perfil del técnico (16 casos)
# =====================================================================
class TestFN9EditarPerfilTecnico(_Base):

    def test_cp_fn9_01_guarda_datos_basicos(self):
        tec = self._tecnico()
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, precio_referencia="60000")
        self.assertEqual(resp.status_code, 302)
        tec.refresh_from_db()
        self.assertEqual(tec.nombre_completo, "Tecnico Editado Prueba")
        self.assertEqual(tec.telefono, "3111111111")
        self.assertEqual(tec.perfil_tecnico.precio_referencia, 60000)

    def test_cp_fn9_02_campos_protegidos_no_se_alteran(self):
        tec = self._tecnico()
        perfil = tec.perfil_tecnico
        perfil.calificacion_promedio = 4.5
        perfil.save(update_fields=["calificacion_promedio"])
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(
            tec, cedula="9999999999", correo="hack@test.co",
            estado="suspendido", rol="administrador", calificacion_promedio="1.0")
        self.assertEqual(resp.status_code, 302)
        tec.refresh_from_db()
        self.assertNotEqual(tec.correo, "hack@test.co")
        self.assertEqual(tec.estado, Usuario.Estado.ACTIVO)
        self.assertEqual(tec.rol, Usuario.Rol.TECNICO)
        perfil.refresh_from_db()
        self.assertEqual(float(perfil.calificacion_promedio), 4.5)

    def test_cp_fn9_03_precio_cero_rechazado(self):
        tec = self._tecnico(precio_referencia=60000)
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, precio_referencia="0")
        self.assertEqual(resp.status_code, 200)
        tec.refresh_from_db()
        self.assertEqual(tec.perfil_tecnico.precio_referencia, 60000)

    def test_cp_fn9_04_precio_negativo_rechazado(self):
        tec = self._tecnico(precio_referencia=60000)
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, precio_referencia="-5")
        self.assertEqual(resp.status_code, 200)
        tec.refresh_from_db()
        self.assertEqual(tec.perfil_tecnico.precio_referencia, 60000)

    def test_cp_fn9_05_precio_vacio_guarda_a_convenir(self):
        tec = self._tecnico(precio_referencia=60000)
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, precio_referencia="")
        self.assertEqual(resp.status_code, 302)
        tec.refresh_from_db()
        self.assertIsNone(tec.perfil_tecnico.precio_referencia)
        self.assertEqual(tec.perfil_tecnico.precio_referencia_txt, "a convenir")

    def test_cp_fn9_06_precio_no_numerico_rechazado(self):
        tec = self._tecnico(precio_referencia=60000)
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, precio_referencia="abc")
        self.assertEqual(resp.status_code, 200)
        tec.refresh_from_db()
        self.assertEqual(tec.perfil_tecnico.precio_referencia, 60000)

    def test_cp_fn9_07_zona_cobertura_obligatoria(self):
        tec = self._tecnico()
        perfil = tec.perfil_tecnico
        perfil.zona_cobertura = "Sur"
        perfil.save(update_fields=["zona_cobertura"])
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, zona_cobertura="")
        self.assertEqual(resp.status_code, 200)
        perfil.refresh_from_db()
        self.assertEqual(perfil.zona_cobertura, "Sur")
        resp = self._post_perfil_tecnico(
            tec, zona_cobertura="Norte de la ciudad")
        self.assertEqual(resp.status_code, 302)
        perfil.refresh_from_db()
        self.assertEqual(perfil.zona_cobertura, "Norte de la ciudad")

    def test_cp_fn9_08_nombre_en_limites_3_y_100(self):
        tec = self._tecnico()
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, nombre_completo="Ana")
        self.assertEqual(resp.status_code, 302)
        resp = self._post_perfil_tecnico(tec, nombre_completo="A" * 100)
        self.assertEqual(resp.status_code, 302)
        resp = self._post_perfil_tecnico(tec, nombre_completo="Li")
        self.assertEqual(resp.status_code, 200)
        resp = self._post_perfil_tecnico(tec, nombre_completo="A" * 101)
        self.assertEqual(resp.status_code, 200)

    def test_cp_fn9_09_telefono_valido_7_a_15_y_letras_rechazadas(self):
        tec = self._tecnico()
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, telefono="3001234")
        self.assertEqual(resp.status_code, 302)
        resp = self._post_perfil_tecnico(tec, telefono="300123456789012")
        self.assertEqual(resp.status_code, 302)
        resp = self._post_perfil_tecnico(tec, telefono="300123")
        self.assertEqual(resp.status_code, 200)
        resp = self._post_perfil_tecnico(tec, telefono="3001234567890123")
        self.assertEqual(resp.status_code, 200)
        resp = self._post_perfil_tecnico(tec, telefono="300ABC4567")
        self.assertEqual(resp.status_code, 200)
        tec.refresh_from_db()
        self.assertNotEqual(tec.telefono, "300ABC4567")

    def test_cp_fn9_10_foto_valida_jpg_se_guarda(self):
        tec = self._tecnico()
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, foto_perfil=_foto("foto.jpg"))
        self.assertEqual(resp.status_code, 302)
        tec.refresh_from_db()
        self.assertTrue(tec.perfil_tecnico.foto_perfil)

    def test_cp_fn9_11_rechaza_gif_y_foto_mayor_de_5mb(self):
        tec = self._tecnico()
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(
            tec, foto_perfil=_foto("foto.gif", formato="GIF"))
        self.assertEqual(resp.status_code, 200)
        tec.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.foto_perfil)
        resp = self._post_perfil_tecnico(tec, foto_perfil=_foto_pesada())
        self.assertEqual(resp.status_code, 200)
        tec.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.foto_perfil)

    def test_cp_fn9_12_cambiar_especialidad_conserva_promedio(self):
        tec = self._tecnico()
        perfil = tec.perfil_tecnico
        perfil.calificacion_promedio = 4.5
        perfil.total_calificaciones = 3
        perfil.save(update_fields=["calificacion_promedio", "total_calificaciones"])
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, especialidad="electricidad")
        self.assertEqual(resp.status_code, 302)
        perfil.refresh_from_db()
        self.assertEqual(perfil.especialidad, "electricidad")
        self.assertEqual(float(perfil.calificacion_promedio), 4.5)
        self.assertEqual(perfil.total_calificaciones, 3)

    def test_cp_fn9_13_precio_actualizado_se_refleja_en_busqueda(self):
        tec = self._tecnico()
        cli = self._cliente(correo="cli@test.co")
        self._solicitud(cli)
        self.client.force_login(tec)
        resp = self._post_perfil_tecnico(tec, precio_referencia="90000")
        self.assertEqual(resp.status_code, 302)
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, "$90.000")

    def test_cp_fn9_14_tecnico_suspendido_no_edita_perfil(self):
        tec = self._tecnico()
        tec.suspender("prueba QA")
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_perfil"))
        self.assertEqual(resp.status_code, 302)

    def test_cp_fn9_15_agrega_certificado_extra(self):
        tec = self._tecnico()
        self.client.force_login(tec)
        resp = self.client.post(reverse("documento_agregar"), {
            "nombre": "Diplomado en redes",
            "especialidad": "electricidad",
            "archivo": _certificado("extra.pdf"),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(DocumentoTecnico.objects.filter(
            perfil=tec.perfil_tecnico, nombre="Diplomado en redes").exists())

    def test_cp_fn9_16_extra_sin_nombre_o_pesado_rechazado(self):
        tec = self._tecnico()
        self.client.force_login(tec)
        resp = self.client.post(reverse("documento_agregar"), {
            "nombre": "", "especialidad": "electricidad",
            "archivo": _certificado("extra.pdf"),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(DocumentoTecnico.objects.count(), 0)
        pesado = b"%PDF-1.4" + b"\0" * (6 * 1024 * 1024)
        resp = self.client.post(reverse("documento_agregar"), {
            "nombre": "Diplomado", "especialidad": "electricidad",
            "archivo": _certificado("big.pdf", pesado),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(DocumentoTecnico.objects.count(), 0)


# =====================================================================
# FN-10: Disponibilidad del técnico (7 casos)
# =====================================================================
class TestFN10Disponibilidad(_Base):

    def test_cp_fn10_01_pausar_lo_quita_de_la_busqueda(self):
        tec = self._tecnico(disponible=True)
        cli = self._cliente(correo="cli@test.co")
        self._solicitud(cli)
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, tec.nombre_completo)
        self.client.force_login(tec)
        resp = self.client.post(reverse("tecnico_disponibilidad"), {})
        self.assertEqual(resp.status_code, 302)
        tec.perfil_tecnico.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.disponible)
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos"))
        self.assertNotContains(resp, tec.nombre_completo)

    def test_cp_fn10_02_reactivar_lo_vuelve_a_mostrar(self):
        tec = self._tecnico(disponible=False)
        cli = self._cliente(correo="cli@test.co")
        self._solicitud(cli)
        self.client.force_login(tec)
        resp = self.client.post(reverse("tecnico_disponibilidad"),
                                {"disponible": "1"})
        self.assertEqual(resp.status_code, 302)
        tec.perfil_tecnico.refresh_from_db()
        self.assertTrue(tec.perfil_tecnico.disponible)
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, tec.nombre_completo)

    def test_cp_fn10_03_en_pausa_persiste_tras_salir_y_entrar(self):
        tec = self._tecnico(disponible=True)
        self.client.force_login(tec)
        self.client.post(reverse("tecnico_disponibilidad"), {})
        self.client.get(reverse("logout"))
        resp = self.client.post(reverse("login"), {
            "correo": tec.correo, "clave": "Clave123!"})
        self.assertEqual(resp.status_code, 302)
        tec.perfil_tecnico.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.disponible)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertContains(resp, "Estás en pausa")

    def test_cp_fn10_04_pausar_no_afecta_servicios_en_curso(self):
        tec = self._tecnico(disponible=True)
        cli = self._cliente(correo="cli@test.co")
        sol = self._solicitud(cli, estado=Solicitud.Estado.EN_CURSO, tecnico=tec)
        self.client.force_login(tec)
        self.client.post(reverse("tecnico_disponibilidad"), {})
        sol.refresh_from_db()
        self.assertEqual(sol.estado, Solicitud.Estado.EN_CURSO)
        self.assertEqual(sol.tecnico, tec)

    def test_cp_fn10_05_pendiente_de_aprobacion_no_puede_activarse(self):
        tec = self._tecnico(estado=Usuario.Estado.PENDIENTE_APROBACION,
                            disponible=False)
        self.client.force_login(tec)
        resp = self.client.post(reverse("tecnico_disponibilidad"),
                                {"disponible": "1"})
        self.assertEqual(resp.status_code, 302)
        tec.perfil_tecnico.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.disponible)

    def test_cp_fn10_06_suspendido_no_puede_reactivarse(self):
        tec = self._tecnico(disponible=True)
        tec.suspender("prueba QA")
        self.client.force_login(tec)
        resp = self.client.post(reverse("tecnico_disponibilidad"),
                                {"disponible": "1"})
        self.assertEqual(resp.status_code, 302)
        tec.perfil_tecnico.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.disponible)

    def test_cp_fn10_07_suspendido_y_pendiente_siguieren_bloqueados(self):
        sus = self._tecnico(correo="sus@test.co", disponible=True)
        sus.suspender("prueba QA")
        pen = self._tecnico(correo="pen@test.co", disponible=False,
                            estado=Usuario.Estado.PENDIENTE_APROBACION)
        self.client.force_login(sus)
        self.client.post(reverse("tecnico_disponibilidad"), {"disponible": "1"})
        sus.perfil_tecnico.refresh_from_db()
        self.assertFalse(sus.perfil_tecnico.disponible)
        self.client.force_login(pen)
        self.client.post(reverse("tecnico_disponibilidad"), {"disponible": "1"})
        pen.perfil_tecnico.refresh_from_db()
        self.assertFalse(pen.perfil_tecnico.disponible)


# =====================================================================
# FN-11: Solicitudes pendientes del técnico (8 casos)
# =====================================================================
class TestFN11SolicitudesPendientes(_Base):

    def _base(self):
        cli = self._cliente(correo="cli@test.co")
        sol = self._solicitud(cli, categoria="plomeria",
                              descripcion="Fuga en la cocina principal.")
        t1 = self._tecnico("t1@test.co", "plomeria", True)
        t2 = self._tecnico("t2@test.co", "electricidad", True)
        t3 = self._tecnico("t3@test.co", "plomeria", False)
        return cli, sol, t1, t2, t3

    def test_cp_fn11_01_ve_las_pendientes_de_su_especialidad(self):
        cli, sol, t1, t2, t3 = self._base()
        self.client.force_login(t1)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertContains(resp, "Fuga en la cocina principal.")
        self.assertContains(resp, sol.direccion)
        self.assertContains(resp, "Plomería")

    def test_cp_fn11_02_no_ve_las_de_otra_especialidad(self):
        cli, sol, t1, t2, t3 = self._base()
        self.client.force_login(t2)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertNotContains(resp, "Fuga en la cocina principal.")

    def test_cp_fn11_03_disponibilidad_inactiva_oculta_las_publicas(self):
        cli, sol, t1, t2, t3 = self._base()
        self.client.force_login(t3)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["solicitudes"]), [])
        self.assertNotContains(resp, "Fuga en la cocina principal.")

    def test_cp_fn11_04_aceptar_la_pone_en_curso(self):
        cli, sol, t1, t2, t3 = self._base()
        self.client.force_login(t1)
        resp = self.client.post(
            reverse("tecnico_aceptar", args=[sol.pk]), {})
        self.assertEqual(resp.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, Solicitud.Estado.EN_CURSO)
        self.assertEqual(sol.tecnico, t1)

    def test_cp_fn11_05_rechazar_la_oculta_para_el_y_queda_para_otros(self):
        cli, sol, t1, t2, t3 = self._base()
        sol2 = self._solicitud(cli, categoria="plomeria",
                               descripcion="Otra fuga en el patio de atrás.")
        self.client.force_login(t1)
        resp = self.client.post(reverse("tecnico_rechazar", args=[sol2.pk]), {})
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertNotContains(resp, "Otra fuga en el patio de atrás.")
        t4 = self._tecnico("t4@test.co", "plomeria", True)
        self.client.force_login(t4)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertContains(resp, "Otra fuga en el patio de atrás.")
        sol2.refresh_from_db()
        self.assertEqual(sol2.estado, Solicitud.Estado.PENDIENTE)

    def test_cp_fn11_06_dos_aceptan_a_la_vez_solo_uno_la_obtiene(self):
        cli, sol, t1, t2, t3 = self._base()
        t4 = self._tecnico("t4@test.co", "plomeria", True)
        self.client.force_login(t1)
        self.client.post(reverse("tecnico_aceptar", args=[sol.pk]), {})
        self.client.force_login(t4)
        resp = self.client.post(
            reverse("tecnico_aceptar", args=[sol.pk]), {}, follow=True)
        self.assertContains(resp, "Otro técnico ya tomó")
        sol.refresh_from_db()
        self.assertEqual(sol.tecnico, t1)
        self.assertEqual(sol.estado, Solicitud.Estado.EN_CURSO)

    def test_cp_fn11_07_bandeja_vacia_muestra_mensaje(self):
        tec = self._tecnico("vacio@test.co", "plomeria", True)
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertContains(resp, "No hay solicitudes por ahora")

    def test_cp_fn11_08_aceptar_una_ya_tomada_muestra_mensaje(self):
        cli, sol, t1, t2, t3 = self._base()
        t4 = self._tecnico("t4@test.co", "plomeria", True)
        self.client.force_login(t1)
        self.client.post(reverse("tecnico_aceptar", args=[sol.pk]), {})
        self.client.force_login(t4)
        resp = self.client.post(
            reverse("tecnico_aceptar", args=[sol.pk]), {}, follow=True)
        self.assertContains(resp, "Otro técnico ya tomó esta solicitud.")
        sol.refresh_from_db()
        self.assertEqual(sol.estado, Solicitud.Estado.EN_CURSO)
        self.assertEqual(sol.tecnico, t1)


# =====================================================================
# Bloque MAP: mapa de solicitudes para técnicos (5 casos)
# =====================================================================
class TestMapaSolicitudes(_Base):

    def _base(self):
        tec = self._tecnico("tec@test.co", "plomeria", True, lat=4.66, lng=-74.07)
        cli = self._cliente(correo="cli@test.co", latitud=4.65, longitud=-74.05)
        sol = self._solicitud(cli, categoria="plomeria",
                              descripcion="Fuga en el mapa de prueba.",
                              precio_ofrecido=50000)
        self.client.force_login(tec)
        return tec, cli, sol

    def test_cp_map_01_mapa_muestra_solicitudes_visibles(self):
        tec, cli, sol = self._base()
        resp = self.client.get(reverse("tecnico_mapa"))
        self.assertEqual(resp.status_code, 200)
        ids = [s["id"] for s in resp.context["solicitudes"]]
        self.assertEqual(ids, [sol.pk])
        self.assertEqual(resp.context["yo_pos"],
                         {"lat": 4.66, "lng": -74.07})

    def test_cp_map_02_bandeja_y_mapa_coinciden(self):
        tec, cli, sol = self._base()
        resp_bandeja = self.client.get(reverse("tecnico_solicitudes"))
        resp_mapa = self.client.get(reverse("tecnico_mapa"))
        ids_bandeja = {s.pk for s in resp_bandeja.context["solicitudes"]}
        ids_mapa = {s["id"] for s in resp_mapa.context["solicitudes"]}
        self.assertEqual(ids_bandeja, ids_mapa)

    def test_cp_map_03_aceptar_desde_el_mapa(self):
        tec, cli, sol = self._base()
        resp = self.client.get(reverse("tecnico_mapa"))
        self.assertContains(resp, "data-aceptar")
        resp = self.client.post(reverse("tecnico_aceptar", args=[sol.pk]), {})
        self.assertEqual(resp.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, Solicitud.Estado.EN_CURSO)

    def test_cp_map_04_popup_muestra_cliente_direccion_precio_y_km(self):
        tec, cli, sol = self._base()
        resp = self.client.get(reverse("tecnico_mapa"))
        self.assertContains(resp, sol.descripcion)
        self.assertContains(resp, "$50.000")
        self.assertContains(resp, " km")

    def test_cp_map_05_tecnico_sin_ubicacion_usa_fallback(self):
        tec, cli, sol = self._base()
        tec2 = self._tecnico("tec2@test.co", "plomeria", True,
                             lat=None, lng=None)
        self.client.force_login(tec2)
        resp = self.client.get(reverse("tecnico_mapa"))
        self.assertTrue(resp.context["mapa_fallback"])
        self.assertContains(resp, "Bogotá")


# =====================================================================
# FN-13: Historial del técnico (6 casos)
# =====================================================================
class TestFN13HistorialTecnico(_Base):

    def _base(self):
        tec = self._tecnico("tec@test.co", "plomeria", True)
        cli = self._cliente(correo="cli@test.co")
        sol1 = self._solicitud(cli, categoria="plomeria",
                               descripcion="Servicio uno en curso.",
                               estado=Solicitud.Estado.EN_CURSO, tecnico=tec)
        sol2 = self._solicitud(cli, categoria="plomeria",
                               descripcion="Servicio dos finalizado.",
                               estado=Solicitud.Estado.EN_CURSO, tecnico=tec)
        self._finalizar(sol2)
        sol3 = self._solicitud(cli, categoria="plomeria",
                               descripcion="Servicio de otro tecnico.",
                               estado=Solicitud.Estado.EN_CURSO,
                               tecnico=self._tecnico("otro@test.co"))
        return tec, cli, sol1, sol2, sol3

    def test_cp_fn13_01_sin_servicios_muestra_mensaje(self):
        tec = self._tecnico("nuevo@test.co", "plomeria", True)
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_historial"))
        self.assertContains(resp, "Aún no tienes servicios")

    def test_cp_fn13_02_muestra_sus_servicios_en_curso(self):
        tec, cli, sol1, sol2, sol3 = self._base()
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_historial"))
        self.assertContains(resp, "Servicio uno en curso.")
        self.assertContains(resp, "fx-badge--en_curso")

    def test_cp_fn13_03_filtro_por_estado_funciona(self):
        tec, cli, sol1, sol2, sol3 = self._base()
        self.client.force_login(tec)
        url = reverse("tecnico_historial")
        resp = self.client.get(f"{url}?estado=en_curso")
        self.assertContains(resp, "Servicio uno en curso.")
        self.assertNotContains(resp, "Servicio dos finalizado.")
        resp = self.client.get(f"{url}?estado=finalizada")
        self.assertContains(resp, "Servicio dos finalizado.")
        self.assertNotContains(resp, "Servicio uno en curso.")
        resp = self.client.get(url)
        self.assertContains(resp, "Servicio uno en curso.")
        self.assertContains(resp, "Servicio dos finalizado.")

    def test_cp_fn13_04_no_muestra_servicios_de_otros_tecnicos(self):
        tec, cli, sol1, sol2, sol3 = self._base()
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_historial"))
        self.assertNotContains(resp, "Servicio de otro tecnico.")

    def test_cp_fn13_05_en_curso_tiene_boton_de_finalizar(self):
        tec, cli, sol1, sol2, sol3 = self._base()
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_historial"))
        self.assertContains(resp, "Finalizar servicio")
        self.assertContains(resp, reverse("tecnico_finalizar", args=[sol1.pk]))
        resp = self.client.get(reverse("tecnico_finalizar", args=[sol1.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_cp_fn13_06_no_muestra_las_pendientes(self):
        tec, cli, sol1, sol2, sol3 = self._base()
        sol_p = self._solicitud(cli, categoria="plomeria",
                                descripcion="Pendiente dirigida a el.",
                                tecnico=tec)
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_historial"))
        self.assertNotContains(resp, "Pendiente dirigida a el.")


# =====================================================================
# FN-15: Suspensión de usuarios (12 casos)
# =====================================================================
class TestFN15SuspenderUsuarios(_Base):

    def _admin_login(self):
        admin = self._admin()
        self.client.force_login(admin)
        return admin

    def test_cp_fn15_01_suspender_con_motivo(self):
        self._admin_login()
        cli = self._cliente()
        resp = self.client.post(reverse("admin_usuarios"), {
            "usuario_id": cli.pk, "accion": "suspender",
            "motivo": "Incumplimiento de pagos."})
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.estado, Usuario.Estado.SUSPENDIDO)
        self.assertEqual(cli.motivo_suspension, "Incumplimiento de pagos.")

    def test_cp_fn15_02_sin_motivo_no_suspende(self):
        self._admin_login()
        cli = self._cliente()
        resp = self.client.post(reverse("admin_usuarios"), {
            "usuario_id": cli.pk, "accion": "suspender"})
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.estado, Usuario.Estado.ACTIVO)

    def test_cp_fn15_03_motivo_de_300_caracteres_aceptado(self):
        self._admin_login()
        cli = self._cliente()
        resp = self.client.post(reverse("admin_usuarios"), {
            "usuario_id": cli.pk, "accion": "suspender", "motivo": "x" * 300})
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.estado, Usuario.Estado.SUSPENDIDO)

    def test_cp_fn15_04_motivo_de_301_caracteres_rechazado(self):
        self._admin_login()
        cli = self._cliente()
        resp = self.client.post(reverse("admin_usuarios"), {
            "usuario_id": cli.pk, "accion": "suspender", "motivo": "x" * 301})
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.estado, Usuario.Estado.ACTIVO)

    def test_cp_fn15_05_suspender_tecnico_lo_vuelve_no_disponible(self):
        self._admin_login()
        tec = self._tecnico(disponible=True)
        resp = self.client.post(reverse("admin_usuarios"), {
            "usuario_id": tec.pk, "accion": "suspender", "motivo": "Conducta."})
        self.assertEqual(resp.status_code, 302)
        tec.perfil_tecnico.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.disponible)

    def test_cp_fn15_06_suspender_tecnico_lo_quita_de_la_busqueda(self):
        self._admin_login()
        tec = self._tecnico(disponible=True)
        cli = self._cliente(correo="cli@test.co")
        self._solicitud(cli)
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos"))
        self.assertContains(resp, tec.nombre_completo)
        self.client.force_login(self._admin())
        self.client.post(reverse("admin_usuarios"), {
            "usuario_id": tec.pk, "accion": "suspender", "motivo": "Conducta."})
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos"))
        nombres = [t["nombre"] for t in resp.context["tecnicos"]]
        self.assertNotIn(tec.nombre_completo, nombres)

    def test_cp_fn15_07_suspendido_no_puede_iniciar_sesion(self):
        cli = self._cliente()
        cli.suspender("prueba QA")
        resp = self.client.post(reverse("login"), {
            "correo": cli.correo, "clave": "Clave123!"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "suspendida")

    def test_cp_fn15_08_suspendido_no_navega_la_app(self):
        cli = self._cliente()
        self.client.force_login(cli)
        cli.suspender("prueba QA")
        resp = self.client.get(reverse("cliente_perfil"))
        self.assertEqual(resp.status_code, 302)

    def test_cp_fn15_09_reactivar_vuelve_a_activo(self):
        self._admin_login()
        cli = self._cliente()
        cli.suspender("prueba QA")
        resp = self.client.post(reverse("admin_usuarios"), {
            "usuario_id": cli.pk, "accion": "reactivar"})
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.estado, Usuario.Estado.ACTIVO)

    def test_cp_fn15_10_reactivar_no_recupera_disponibilidad(self):
        self._admin_login()
        tec = self._tecnico(disponible=True)
        self.client.post(reverse("admin_usuarios"), {
            "usuario_id": tec.pk, "accion": "suspender", "motivo": "Conducta."})
        self.client.post(reverse("admin_usuarios"), {
            "usuario_id": tec.pk, "accion": "reactivar"})
        tec.refresh_from_db()
        self.assertEqual(tec.estado, Usuario.Estado.ACTIVO)
        tec.perfil_tecnico.refresh_from_db()
        self.assertFalse(tec.perfil_tecnico.disponible)

    def test_cp_fn15_11_suspender_tecnico_libera_sus_en_curso(self):
        self._admin_login()
        tec = self._tecnico(disponible=True)
        cli = self._cliente(correo="cli@test.co")
        sol = self._solicitud(cli, estado=Solicitud.Estado.EN_CURSO, tecnico=tec)
        resp = self.client.post(reverse("admin_usuarios"), {
            "usuario_id": tec.pk, "accion": "suspender", "motivo": "Conducta."})
        self.assertEqual(resp.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, Solicitud.Estado.PENDIENTE)
        self.assertIsNone(sol.tecnico)
        self.assertTrue(Notificacion.objects.filter(
            usuario=cli, tipo=Notificacion.Tipo.SOLICITUD_LIBERADA,
            solicitud=sol).exists())

    def test_cp_fn15_12_cliente_no_accede_al_panel(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.get(reverse("admin_usuarios"))
        self.assertEqual(resp.status_code, 403)


# =====================================================================
# FN-16: Reportes del admin (11 casos)
# =====================================================================
class TestFN16Reportes(_Base):

    def _datos(self):
        admin = self._admin()
        cli = self._cliente(correo="cli@test.co")
        t_ok = self._tecnico("tok@test.co", disponible=True)
        self._tecnico("tsus@test.co", disponible=False,
                      estado=Usuario.Estado.SUSPENDIDO)
        self._tecnico("tpen@test.co", disponible=False,
                      estado=Usuario.Estado.PENDIENTE_APROBACION)
        ahora = timezone.now()
        hace60 = ahora - timedelta(days=60)
        f1 = self._solicitud(cli, "plomeria", "Fuga uno en la cocina.",
                             estado=Solicitud.Estado.EN_CURSO, tecnico=t_ok)
        self._finalizar(f1, monto=10000)
        f2 = self._solicitud(cli, "electricidad", "Corto dos en la sala.",
                             estado=Solicitud.Estado.EN_CURSO, tecnico=t_ok)
        self._finalizar(f2, monto=10000)
        f3 = self._solicitud(cli, "cerrajeria", "Chapa tres de la entrada.")
        Solicitud.objects.filter(pk=f3.pk).update(
            estado=Solicitud.Estado.FINALIZADA,
            fecha_finalizacion=hace60, monto_final=5000)
        for solicitud in (f1, f2):
            pago = Pago.objects.create(
                solicitud=solicitud, medio_pago=Pago.Medio.TARJETA, monto=10000)
            pago.marcar_exitoso("SIM-TEST")
        pago_viejo = Pago.objects.create(
            solicitud=f3, medio_pago=Pago.Medio.EFECTIVO, monto=5000)
        pago_viejo.marcar_exitoso("SIM-VIEJO")
        Pago.objects.filter(pk=pago_viejo.pk).update(fecha_creacion=hace60)
        Comision.objects.filter(pago=pago_viejo).update(fecha_calculo=hace60)
        self.client.force_login(admin)
        return {"admin": admin, "cli": cli, "t_ok": t_ok, "f1": f1,
                "f2": f2, "f3": f3, "ahora": ahora, "hace60": hace60}

    def test_cp_fn16_01_rango_por_defecto_ultimos_30_dias(self):
        self._datos()
        resp = self.client.get(reverse("admin_reportes"))
        hoy = timezone.localdate()
        self.assertEqual(resp.context["desde"], (hoy - timedelta(days=30)).isoformat())
        self.assertEqual(resp.context["hasta"], hoy.isoformat())

    def test_cp_fn16_02_servicios_finalizados_en_el_rango(self):
        datos = self._datos()
        resp = self.client.get(reverse("admin_reportes"))
        self.assertEqual(resp.context["servicios_finalizados"], 2)
        hoy = timezone.localdate()
        url = (f"{reverse('admin_reportes')}?desde={datos['hace60'].date().isoformat()}"
               f"&hasta={hoy.isoformat()}")
        resp = self.client.get(url)
        self.assertEqual(resp.context["servicios_finalizados"], 3)

    def test_cp_fn16_03_rango_invertido_se_corrige(self):
        self._datos()
        hoy = timezone.localdate()
        url = (f"{reverse('admin_reportes')}?desde={hoy.isoformat()}"
               f"&hasta={(hoy - timedelta(days=30)).isoformat()}")
        resp = self.client.get(url)
        self.assertEqual(resp.context["desde"],
                         (hoy - timedelta(days=30)).isoformat())
        self.assertEqual(resp.context["hasta"], hoy.isoformat())

    def test_cp_fn16_04_rango_de_un_dia_solo_cuenta_ese_dia(self):
        self._datos()
        hoy = timezone.localdate()
        url = (f"{reverse('admin_reportes')}?desde={hoy.isoformat()}"
               f"&hasta={hoy.isoformat()}")
        resp = self.client.get(url)
        self.assertEqual(resp.context["servicios_finalizados"], 2)

    def test_cp_fn16_05_interfaz_tiene_boton_de_30_dias(self):
        self._datos()
        resp = self.client.get(reverse("admin_reportes"))
        self.assertContains(resp, "Últimos 30 días")

    def test_cp_fn16_06_cuenta_coincide_con_la_base_de_datos(self):
        self._datos()
        resp = self.client.get(reverse("admin_reportes"))
        hoy = timezone.localdate()
        inicio = timezone.make_aware(
            datetime.combine(hoy - timedelta(days=30), datetime.min.time()))
        fin = timezone.make_aware(
            datetime.combine(hoy + timedelta(days=1), datetime.min.time()))
        esperado = Solicitud.objects.filter(
            estado=Solicitud.Estado.FINALIZADA,
            fecha_finalizacion__gte=inicio,
            fecha_finalizacion__lt=fin,
        ).count()
        self.assertEqual(resp.context["servicios_finalizados"], esperado)
        self.assertEqual(resp.context["servicios_finalizados"], 2)

    def test_cp_fn16_07_tecnicos_activos_solo_cuenta_aprobados(self):
        self._datos()
        resp = self.client.get(reverse("admin_reportes"))
        self.assertEqual(resp.context["tecnicos_activos"], 1)

    def test_cp_fn16_08_suma_de_comisiones_del_rango(self):
        self._datos()
        resp = self.client.get(reverse("admin_reportes"))
        self.assertEqual(resp.context["comisiones_suma"], 2000)

    def test_cp_fn16_09_usuarios_activos_y_suspendidos_se_actualizan(self):
        datos = self._datos()
        resp = self.client.get(reverse("admin_reportes"))
        self.assertEqual(resp.context["usuarios_suspendidos"], 1)
        activos_antes = resp.context["usuarios_activos"]
        datos["cli"].suspender("prueba QA")
        resp = self.client.get(reverse("admin_reportes"))
        self.assertEqual(resp.context["usuarios_suspendidos"], 2)
        self.assertEqual(resp.context["usuarios_activos"], activos_antes - 1)

    def test_cp_fn16_10_solo_lectura_post_no_cambia_datos(self):
        self._datos()
        solicitudes_antes = Solicitud.objects.count()
        pagos_antes = Pago.objects.count()
        resp = self.client.post(reverse("admin_reportes"), {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Solicitud.objects.count(), solicitudes_antes)
        self.assertEqual(Pago.objects.count(), pagos_antes)

    def test_cp_fn16_11_cliente_no_accede_a_reportes(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.get(reverse("admin_reportes"))
        self.assertEqual(resp.status_code, 403)


# =====================================================================
# RES/IA: Moderación de reseñas e IA de categorías (7 casos)
# =====================================================================
class TestResenasIA(_Base):

    def _tec_con_resenas(self):
        tec = self._tecnico("tec@test.co", "plomeria", True)
        cli = self._cliente(correo="cli@test.co")
        s1 = self._solicitud(cli, estado=Solicitud.Estado.EN_CURSO, tecnico=tec)
        self._finalizar(s1)
        s2 = self._solicitud(cli, estado=Solicitud.Estado.EN_CURSO, tecnico=tec)
        self._finalizar(s2)
        return tec, cli, s1, s2

    def test_cp_res_01_ocultar_recalcula_el_promedio(self):
        tec, cli, s1, s2 = self._tec_con_resenas()
        self._calificacion(s1, 5, "Excelente trabajo")
        resena_mala = self._calificacion(s2, 1, "Muy mal servicio")
        tec.perfil_tecnico.refresh_from_db()
        self.assertEqual(float(tec.perfil_tecnico.calificacion_promedio), 3.0)
        self.assertEqual(tec.perfil_tecnico.total_calificaciones, 2)
        admin = self._admin()
        self.client.force_login(admin)
        resp = self.client.post(reverse("resena_moderar"), {
            "resena_id": resena_mala.pk, "accion": "ocultar"})
        self.assertEqual(resp.status_code, 302)
        resena_mala.refresh_from_db()
        self.assertTrue(resena_mala.oculta)
        tec.perfil_tecnico.refresh_from_db()
        self.assertEqual(float(tec.perfil_tecnico.calificacion_promedio), 5.0)
        self.assertEqual(tec.perfil_tecnico.total_calificaciones, 1)

    def test_cp_res_02_filtros_de_moderacion(self):
        tec, cli, s1, s2 = self._tec_con_resenas()
        s3 = self._solicitud(cli, estado=Solicitud.Estado.EN_CURSO, tecnico=tec)
        self._finalizar(s3)
        self._calificacion(s1, 4, "Buena labor")
        r2 = self._calificacion(s2, 2, "Texto en revision")
        r2.revision_admin = True
        r2.save(update_fields=["revision_admin"])
        r3 = self._calificacion(s3, 1, "Texto oculto")
        r3.oculta = True
        r3.save(update_fields=["oculta"])
        self.client.force_login(self._admin())
        url = reverse("admin_resenas")
        resp = self.client.get(url)
        self.assertContains(resp, "Buena labor")
        self.assertContains(resp, "Texto en revision")
        self.assertContains(resp, "Texto oculto")
        resp = self.client.get(f"{url}?filtro=revision")
        self.assertContains(resp, "Texto en revision")
        self.assertNotContains(resp, "Buena labor")
        self.assertNotContains(resp, "Texto oculto")
        resp = self.client.get(f"{url}?filtro=ocultas")
        self.assertContains(resp, "Texto oculto")
        self.assertNotContains(resp, "Buena labor")

    def test_cp_res_03_perfil_publico_no_muestra_ocultas(self):
        tec, cli, s1, s2 = self._tec_con_resenas()
        self._calificacion(s1, 4, "Buena labor")
        r2 = self._calificacion(s2, 1, "Texto oculto")
        r2.oculta = True
        r2.save(update_fields=["oculta"])
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnico_publico", args=[tec.pk]))
        self.assertNotContains(resp, "Texto oculto")
        self.assertContains(resp, "Buena labor")

    def test_cp_ia_01_sugiere_plomeria_para_fuga(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.get(reverse("sugerir_categoria"),
                               {"texto": "fuga de agua en la cocina"})
        datos = resp.json()
        self.assertEqual(datos["categoria"], "plomeria")
        self.assertTrue(datos["ia_disponible"])

    def test_cp_ia_02_texto_irrelevante_no_sugiere_nada(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.get(reverse("sugerir_categoria"),
                               {"texto": "Hola buenos días tardes"})
        self.assertIsNone(resp.json()["categoria"])

    def test_cp_ia_03_crear_solicitud_deja_muestra_de_aprendizaje(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.post(reverse("solicitud_nueva"), {
            "categoria": "plomeria",
            "descripcion": "El tanque del bano pierde agua por la base y no llena",
            "direccion": "Cra 13 #52-40",
            "urgencia": "normal",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(IASugerencia.objects.filter(
            categoria_final="plomeria").exists())

    def test_cp_ia_04_reentrenar_muestra_confirmacion(self):
        admin = self._admin()
        self.client.force_login(admin)
        resp = self.client.post(reverse("admin_ia"), {}, follow=True)
        self.assertContains(resp, "reiniciado")
