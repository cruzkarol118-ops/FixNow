"""Bloque F4 — pruebas Django por bloque (A–E + F) + Bloque G.

Usan la BD de test (no tocan fixnow_db): al menos 1 test por bloque.
Se corren con: .\\.venv\\Scripts\\python.exe manage.py test
"""

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.ia import analizar_sentimiento, predecir_categoria
from core.models import (
    Calificacion, Comision, DocumentoTecnico, Notificacion, Pago,
    PerfilTecnico, Solicitud, Usuario,
)

import tempfile


def _certificado(nombre="cert.pdf"):
    return SimpleUploadedFile(nombre, b"%PDF-1.4 demo", content_type="application/pdf")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="fixnow-test-media-"))
class _Base(TestCase):
    """Fábricas mínimas: clientes, técnicos con perfil y un admin staff.

    MEDIA_ROOT apunta a un temporal para no ensuciar media/ del repo.
    """

    n = 0

    def _usuario(self, rol, correo, estado=Usuario.Estado.ACTIVO, password="Clave123!",
                 staff=False):
        type(self).n += 1
        return Usuario.objects.create_user(
            correo=correo, password=password,
            cedula=f"{70000000 + type(self).n}",
            nombre_completo=f"Prueba {correo}",
            telefono="3000000000", rol=rol, estado=estado,
            direccion="Cra 13 #52-40", is_staff=staff,
            is_superuser=staff,
        )

    def _cliente(self, correo="cli@test.co", **kw):
        return self._usuario(Usuario.Rol.CLIENTE, correo, **kw)

    def _tecnico(self, correo, especialidad="plomeria", disponible=True, **kw):
        usuario = self._usuario(Usuario.Rol.TECNICO, correo, **kw)
        PerfilTecnico.objects.create(
            usuario=usuario, especialidad=especialidad, ciudad="Bogotá",
            documento_certificacion=_certificado(f"cert-{correo}.pdf"),
            disponible=disponible, precio_referencia=60000,
        )
        return usuario

    def _solicitud(self, cliente, categoria="plomeria", descripcion="Fuga de agua bajo el lavaplatos."):
        return Solicitud.objects.create(
            cliente=cliente, categoria=categoria, descripcion=descripcion,
            direccion="Cra 13 #52-40", urgencia=Solicitud.Urgencia.NORMAL,
        )


# ---------- Bloque A: auth real ----------
class BloqueATest(_Base):
    def test_login_ok_redirige(self):
        self._cliente()
        resp = self.client.post(reverse("login"), {"correo": "cli@test.co", "clave": "Clave123!"})
        self.assertEqual(resp.status_code, 302)

    def test_login_malo_devuelve_200_con_error(self):
        self._cliente()
        resp = self.client.post(reverse("login"), {"correo": "cli@test.co", "clave": "Mala999!"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "incorrectos")

    def test_guard_anonimo_redirige_a_login(self):
        resp = self.client.get(reverse("cliente_inicio"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp["Location"])

    def test_cliente_no_entra_al_panel(self):
        self._cliente()
        self.client.force_login(Usuario.objects.get(correo="cli@test.co"))
        resp = self.client.get(reverse("admin_tecnicos"))
        self.assertIn(resp.status_code, (302, 403))

    def test_suspendido_no_entra(self):
        cli = self._cliente()
        cli.suspender("prueba QA")
        resp = self.client.post(reverse("login"), {"correo": "cli@test.co", "clave": "Clave123!"})
        self.assertEqual(resp.status_code, 200)  # no hay redirect: no entró


# ---------- Validación de nombre según documentos (FN-1/FN-2/FN-8/FN-9) ----------
class NombreValidationTest(_Base):
    def _registro(self, **cambios):
        datos = {
            "cedula": "1098765432", "nombre_completo": "María Fernanda Rojas",
            "correo": "nuevo@test.co", "telefono": "3001234567",
            "password": "Clave123!", "password2": "Clave123!", "terminos": "on",
        }
        datos.update(cambios)
        return self.client.post(reverse("registro_cliente"), datos)

    def test_nombre_valido_pasa(self):
        resp = self._registro()
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Usuario.objects.filter(correo="nuevo@test.co").exists())

    def test_nombre_corto_o_con_numeros_rebota(self):
        for nombre in ("Li", "Juan123", "!!!"):
            resp = self._registro(
                nombre_completo=nombre,
                correo=f"n{abs(hash(nombre)) % 100000}@test.co")
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(Usuario.objects.filter(nombre_completo=nombre).exists())


# ---------- Bloque B: perfiles y administración ----------
class BloqueBTest(_Base):
    def test_editar_perfil_cliente_persiste(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.post(reverse("cliente_perfil"), {
            "nombre_completo": "Prueba Cliente", "telefono": "3111111111",
            "direccion": "Cl 63 #9-15", "fecha_nacimiento": "1990-01-01",
        })
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.direccion, "Cl 63 #9-15")

    def test_admin_aprueba_tecnico_y_notifica(self):
        admin = self._cliente(correo="admin@test.co", staff=True)
        tec = self._tecnico("nuevo@test.co", disponible=False,
                            estado=Usuario.Estado.PENDIENTE_APROBACION)
        self.client.force_login(admin)
        resp = self.client.post(reverse("admin_tecnicos"), {
            "tecnico_id": tec.pk, "accion": "aprobar", "motivo": "",
        })
        self.assertEqual(resp.status_code, 302)
        tec.refresh_from_db()
        self.assertEqual(tec.estado, Usuario.Estado.ACTIVO)
        self.assertFalse(tec.perfil_tecnico.disponible)  # aprobado ≠ disponible
        self.assertTrue(Notificacion.objects.filter(
            usuario=tec, tipo=Notificacion.Tipo.TECNICO_APROBADO).exists())

    def test_rechazar_sin_motivo_da_error(self):
        admin = self._cliente(correo="admin@test.co", staff=True)
        tec = self._tecnico("nuevo@test.co",
                            estado=Usuario.Estado.PENDIENTE_APROBACION)
        self.client.force_login(admin)
        self.client.post(reverse("admin_tecnicos"), {
            "tecnico_id": tec.pk, "accion": "rechazar", "motivo": "",
        })
        tec.refresh_from_db()
        self.assertEqual(tec.estado, Usuario.Estado.PENDIENTE_APROBACION)


# ---------- Bloque C: ciclo operativo ----------
class BloqueCTest(_Base):
    def test_crear_solicitud_queda_pendiente(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.post(reverse("solicitud_nueva"), {
            "categoria": "plomeria",
            "descripcion": "Hay una fuga de agua bajo el lavaplatos.",
            "direccion": "Cra 13 #52-40", "urgencia": "normal",
        })
        self.assertEqual(resp.status_code, 302)
        sol = Solicitud.objects.get(cliente=cli)
        self.assertEqual(sol.estado, Solicitud.Estado.PENDIENTE)

    def test_aceptar_atomico_sin_carrera(self):
        cli = self._cliente()
        t1 = self._tecnico("t1@test.co")
        t2 = self._tecnico("t2@test.co")
        sol = self._solicitud(cli)
        sol.aceptar(t1)
        with self.assertRaises(ValueError):
            sol.aceptar(t2)  # el segundo pierde la carrera
        sol.refresh_from_db()
        self.assertEqual(sol.tecnico, t1)
        self.assertEqual(sol.estado, Solicitud.Estado.EN_CURSO)

    def test_finalizar_con_monto_y_otro_tecnico_403(self):
        cli = self._cliente()
        t1 = self._tecnico("t1@test.co")
        t2 = self._tecnico("t2@test.co")
        sol = self._solicitud(cli)
        sol.aceptar(t1)
        # Otro técnico no puede finalizarla.
        self.client.force_login(t2)
        resp = self.client.post(reverse("tecnico_finalizar", args=[sol.pk]), {
            "monto": "60000", "notas": "Listo.",
        })
        self.assertEqual(resp.status_code, 403)
        # El asignado sí, y el monto queda guardado.
        self.client.force_login(t1)
        resp = self.client.post(reverse("tecnico_finalizar", args=[sol.pk]), {
            "monto": "60000", "notas": "Listo.",
        })
        self.assertEqual(resp.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, Solicitud.Estado.FINALIZADA)
        self.assertEqual(sol.monto_final, 60000)

    def test_cancelar_pendiente_si_en_curso_no(self):
        cli = self._cliente()
        t1 = self._tecnico("t1@test.co")
        self.client.force_login(cli)
        sol = self._solicitud(cli)
        resp = self.client.post(reverse("solicitud_cancelar", args=[sol.pk]))
        self.assertEqual(resp.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, Solicitud.Estado.CANCELADA)
        sol2 = self._solicitud(cli)
        sol2.aceptar(t1)
        resp = self.client.post(reverse("solicitud_cancelar", args=[sol2.pk]))
        self.assertEqual(resp.status_code, 403)


# ---------- Bloque D: cierre del ciclo ----------
class BloqueDTest(_Base):
    def _finalizada(self, cli=None, tec=None):
        cli = cli or self._cliente()
        tec = tec or self._tecnico("t1@test.co")
        sol = self._solicitud(cli)
        sol.aceptar(tec)
        sol.finalizar(notas="Listo.", monto_final=80000)
        return sol

    def test_calificar_una_vez_y_promedio(self):
        cli = self._cliente()
        tec = self._tecnico("t1@test.co")
        sol = self._finalizada(cli, tec)
        self.client.force_login(cli)
        url = reverse("solicitud_calificar", args=[sol.pk])
        resp = self.client.post(url, {"estrellas": "5", "comentario": "Excelente, puntual y amable."})
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(url, {"estrellas": "4", "comentario": "Otra vez."})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Calificacion.objects.filter(solicitud=sol).count(), 1)
        tec.perfil_tecnico.refresh_from_db()
        self.assertEqual(float(tec.perfil_tecnico.calificacion_promedio), 5.0)

    def test_calificar_con_insulto_queda_en_revision_y_avisa_admin(self):
        self._cliente(correo="admin@test.co", staff=True)
        cli = self._cliente()
        tec = self._tecnico("t1@test.co")
        sol = self._finalizada(cli, tec)
        self.client.force_login(cli)
        self.client.post(reverse("solicitud_calificar", args=[sol.pk]), {
            "estrellas": "1", "comentario": "Eres un idiota, pesimo servicio, una porqueria.",
        })
        cal = Calificacion.objects.get(solicitud=sol)
        self.assertTrue(cal.revision_admin)
        admin = Usuario.objects.get(correo="admin@test.co")
        self.assertTrue(Notificacion.objects.filter(
            usuario=admin,
            tipo=Notificacion.Tipo.CALIFICACION_ALERTA).exists())


# ---------- Bloque E: dinero ----------
class BloqueETest(_Base):
    def _finalizada_con_monto(self, monto=100000):
        cli = self._cliente()
        tec = self._tecnico("t1@test.co")
        sol = self._solicitud(cli)
        sol.aceptar(tec)
        sol.finalizar(notas="Listo.", monto_final=monto)
        return sol

    def test_pago_exitoso_crea_comision_que_cuadra(self):
        sol = self._finalizada_con_monto(100000)
        self.client.force_login(sol.cliente)
        # Bloque H: el pago exige monto aceptado.
        self.client.post(reverse("monto_decidir"), {
            "solicitud_id": sol.pk, "accion": "aceptar_monto"})
        resp = self.client.post(reverse("solicitud_pagar", args=[sol.pk]), {
            "medio": "pse", "resultado": "exito",
        })
        self.assertEqual(resp.status_code, 302)
        pago = Pago.objects.get(solicitud=sol)
        self.assertEqual(pago.estado, Pago.Estado.EXITOSO)
        comision = Comision.objects.get(pago=pago)
        self.assertEqual(comision.monto_comision + comision.monto_neto_tecnico, 100000)
        self.assertEqual(comision.monto_comision, 10000)  # 10 % por defecto
        # Pago duplicado bloqueado: sigue habiendo un solo pago.
        self.client.post(reverse("solicitud_pagar", args=[sol.pk]), {
            "medio": "pse", "resultado": "exito",
        })
        self.assertEqual(Pago.objects.filter(solicitud=sol).count(), 1)

    def test_reporte_abre_para_staff(self):
        admin = self._cliente(correo="admin@test.co", staff=True)
        self.client.force_login(admin)
        resp = self.client.get(reverse("admin_reportes"))
        self.assertEqual(resp.status_code, 200)


# ---------- Bloque F: IA + endurecimiento ----------
class BloqueFTest(_Base):
    def test_ia_sugiere_plomeria_ante_fuga(self):
        try:
            import sklearn  # noqa: F401
        except ImportError:
            self.skipTest("scikit-learn no instalado")
        cat, margen = predecir_categoria("Hay un goteo bajo el lavamanos del bano")
        self.assertEqual(cat, "plomeria")
        self.assertGreaterEqual(margen, 0.10)

    def test_ia_no_bloquea_formulario_y_sugiere_en_vista(self):
        cli = self._cliente()
        self.client.force_login(cli)
        # POST sin categoría pero con descripción: 200 + aviso, sin crear.
        resp = self.client.post(reverse("solicitud_nueva"), {
            "descripcion": "Hay un goteo bajo el lavamanos del bano.",
            "direccion": "Cra 13 #52-40", "urgencia": "normal",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Solicitud.objects.filter(cliente=cli).exists())
        try:
            import sklearn  # noqa: F401
        except ImportError:
            return  # sin IA no hay aviso, pero el formulario no se bloqueó
        self.assertContains(resp, "IA sugiere:")

    def test_sentimiento_alerta_ante_insulto(self):
        polaridad, alerta = analizar_sentimiento(
            "Eres un idiota, pesimo servicio, una porqueria.", estrellas=1)
        self.assertTrue(alerta)
        _pol, alerta_ok = analizar_sentimiento(
            "Excelente trabajo, muy puntual y amable.", estrellas=5)
        self.assertFalse(alerta_ok)

    def test_sentimiento_entiende_negaciones(self):
        # "no fue malo" no es negativo: la negación invierte.
        _pol, alerta = analizar_sentimiento(
            "No fue malo, buen trabajo.", estrellas=5)
        self.assertFalse(alerta)

    def test_sentimiento_un_insulto_suelto_no_alerta_si_hay_elogio(self):
        # Falso positivo del usuario: insulto aislado entre elogios.
        _pol, alerta = analizar_sentimiento(
            "Habia una jodida fuga horrible pero quedo bien reparada. Muy bien.",
            estrellas=4)
        self.assertFalse(alerta)
        # Pero un insulto sin nada positivo sí alerta.
        _pol2, alerta2 = analizar_sentimiento("Eres un idiota.", estrellas=1)
        self.assertTrue(alerta2)

    def test_clasificador_calla_ante_duda(self):
        cat, _margen = predecir_categoria("hola buenas tardes")
        self.assertIsNone(cat)

    def test_una_palabra_suelta_nunca_sugiere(self):
        # El fuzzy daba 100 a cualquier palabra contenida en una frase y ganaba
        # la primera del archivo (arbitrario): piso mínimo de 3 tokens.
        for texto in ("ventilador", "hola", "ducha"):
            cat, _m = predecir_categoria(texto)
            self.assertIsNone(cat)

    def test_criterio_verbo_aparato_vs_trabajo(self):
        casos = [
            ("instalar un ventilador de techo", "electricidad"),
            ("cablear la ducha electrica", "electricidad"),
            ("el ventilador no gira", "electrodomesticos"),
            ("la ducha electrica no calienta", "electrodomesticos"),
        ]
        for texto, esperado in casos:
            cat, _m = predecir_categoria(texto)
            self.assertEqual(cat, esperado)

    def test_stemming_une_conjugaciones(self):
        # "repararlo" y "reparar" confluyen; el caso del usuario sugiere.
        cat, _m = predecir_categoria(
            "Se estropeo mi computador, necesito repararlo")
        self.assertEqual(cat, "electrodomesticos")

    def test_clasificador_sugiere_casos_reales(self):
        for texto, esperado in [
            ("Se estallo la regadera", "plomeria"),
            ("Se dano un bombillo", "electricidad"),
            ("Se dano el microondas", "electrodomesticos"),
        ]:
            cat, _m = predecir_categoria(texto)
            self.assertEqual(cat, esperado)

    def test_fuzzy_rescata_typos_y_calla_ante_basura(self):
        try:
            import rapidfuzz  # noqa: F401
        except ImportError:
            self.skipTest("rapidfuzz no instalado")
        cat, _m = predecir_categoria("se danio el microhondas")
        self.assertEqual(cat, "electrodomesticos")
        cat2, _m2 = predecir_categoria("necesito un tecnico urgente ya")
        self.assertIsNone(cat2)

    def test_revision_se_puede_quitar(self):
        from core.models import Calificacion
        cli = self._cliente()
        tec = self._tecnico("trev@test.co")
        sol = self._solicitud(cli)
        sol.tecnico = tec
        sol.estado = Solicitud.Estado.FINALIZADA
        sol.save()
        cal = Calificacion.objects.create(
            solicitud=sol, estrellas=1, comentario="Malo.",
            revision_admin=True)
        adm = self._usuario(Usuario.Rol.CLIENTE, "adm2@test.co", staff=True)
        self.client.force_login(adm)
        resp = self.client.post(reverse("resena_moderar"), {
            "resena_id": cal.pk, "accion": "revisada"})
        self.assertEqual(resp.status_code, 302)
        cal.refresh_from_db()
        self.assertFalse(cal.revision_admin)
        self.assertFalse(cal.oculta)

    def test_modo_estricto_en_conexion(self):
        opciones = settings.DATABASES["default"].get("OPTIONS", {})
        self.assertIn("STRICT_TRANS_TABLES", opciones.get("init_command", ""))


class BloqueGTest(_Base):
    def _pendiente(self, correo="rev@test.co"):
        tec = self._usuario(Usuario.Rol.TECNICO, correo,
                            estado=Usuario.Estado.PENDIENTE_APROBACION)
        PerfilTecnico.objects.create(
            usuario=tec, especialidad="plomeria", ciudad="Bogotá",
            documento_certificacion=_certificado(f"cert-{correo}.pdf"))
        return tec

    def test_reabrir_vuelve_a_pendiente_y_apaga(self):
        adm = self._usuario(Usuario.Rol.CLIENTE, "adm@test.co", staff=True)
        tec = self._pendiente()
        self.client.force_login(adm)
        self.client.post(reverse("admin_tecnicos"),
                         {"tecnico_id": tec.pk, "accion": "aprobar"})
        tec.refresh_from_db()
        self.assertEqual(tec.estado, "activo")
        self.client.post(reverse("admin_tecnicos"),
                         {"tecnico_id": tec.pk, "accion": "reabrir",
                          "motivo": "me equivoqué"})
        tec.refresh_from_db()
        self.assertEqual(tec.estado, "pendiente_aprobacion")
        self.assertFalse(tec.perfil_tecnico.disponible)
        self.assertTrue(Notificacion.objects.filter(
            usuario=tec, tipo=Notificacion.Tipo.TECNICO_REABIERTO).exists())

    def test_ocultar_resena_recalcula_promedio(self):
        cli = self._cliente()
        tec = self._tecnico("tec@test.co")
        sol = self._solicitud(cli)
        sol.tecnico = tec
        sol.estado = Solicitud.Estado.FINALIZADA
        sol.save()
        cal = Calificacion.objects.create(
            solicitud=sol, estrellas=5, comentario="Buen trabajo")
        perfil = PerfilTecnico.objects.get(usuario=tec)
        self.assertEqual(float(perfil.calificacion_promedio), 5.0)
        adm = self._usuario(Usuario.Rol.CLIENTE, "adm@test.co", staff=True)
        self.client.force_login(adm)
        resp = self.client.post(reverse("resena_moderar"),
                                {"resena_id": cal.pk, "accion": "ocultar"})
        self.assertEqual(resp.status_code, 302)
        cal.refresh_from_db()
        self.assertTrue(cal.oculta)
        perfil.refresh_from_db()
        self.assertEqual(float(perfil.calificacion_promedio), 0)
        # Y ya no sale en el perfil público.
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnico_publico", args=[tec.pk]))
        self.assertNotContains(resp, "Buen trabajo")

    def test_desactivar_bloquea_y_reactivar_devuelve(self):
        cli = self._cliente()
        self.client.force_login(cli)
        resp = self.client.post(reverse("cuenta_desactivar"),
                                {"password": "Clave123!"})
        self.assertEqual(resp.status_code, 302)
        cli.refresh_from_db()
        self.assertEqual(cli.estado, "inactivo")
        resp = self.client.post(reverse("login"),
                                {"correo": cli.correo, "clave": "Clave123!"})
        self.assertIsNone(resp.get("Location"))  # 200 con error, sin redirect
        adm = self._usuario(Usuario.Rol.CLIENTE, "adm@test.co", staff=True)
        self.client.force_login(adm)
        self.client.post(reverse("admin_usuarios"),
                         {"usuario_id": cli.pk, "accion": "reactivar"})
        cli.refresh_from_db()
        self.assertEqual(cli.estado, "activo")

    def test_documento_agregar_y_eliminar_solo_dueno(self):
        tec = self._tecnico("tec@test.co")
        otro = self._tecnico("otro@test.co")
        self.client.force_login(tec)
        resp = self.client.post(reverse("documento_agregar"), {
            "nombre": "Curso X",
            "especialidad": "electricidad",
            "archivo": _certificado("curso.pdf"),
        })
        self.assertEqual(resp.status_code, 302)
        doc = DocumentoTecnico.objects.get(perfil__usuario=tec)
        self.assertEqual(doc.nombre, "Curso X")
        # Otro técnico no puede borrarlo (404, sigue existiendo).
        self.client.force_login(otro)
        resp = self.client.post(
            reverse("documento_eliminar", args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(DocumentoTecnico.objects.filter(pk=doc.pk).exists())
        self.client.force_login(tec)
        self.client.post(reverse("documento_eliminar", args=[doc.pk]))
        self.assertFalse(DocumentoTecnico.objects.filter(pk=doc.pk).exists())


class BloqueHITest(_Base):
    def _flujo(self):
        cli = self._cliente("hcli@test.co")
        tec = self._tecnico("htec@test.co")
        sol = Solicitud.objects.create(
            cliente=cli, categoria="plomeria",
            descripcion="Fuga de agua bajo el lavaplatos.",
            direccion="Cra 13 #52-40", urgencia="normal",
            precio_ofrecido=70000, visible_tecnicos=True)
        return cli, tec, sol

    def test_elegir_sin_pendiente_va_a_crear_dirigida(self):
        cli = self._cliente()
        tec = self._tecnico("htec@test.co")
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos") + f"?elegir={tec.pk}")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"tecnico={tec.pk}", resp["Location"])

    def test_crear_dirigida_y_tercero_no_la_toma(self):
        cli, tec, _ = self._flujo()
        otro = self._tecnico("hotro@test.co")
        sol = Solicitud.objects.create(
            cliente=cli, categoria="plomeria",
            descripcion="Otra fuga bajo el lavamanos.",
            direccion="Cra 13 #52-40", urgencia="normal", tecnico=tec)
        self.client.force_login(otro)
        self.client.post(reverse("tecnico_aceptar", args=[sol.pk]))
        sol.refresh_from_db()
        self.assertEqual(sol.estado, "pendiente")
        self.assertEqual(sol.tecnico_id, tec.pk)
        # El dirigido sí puede.
        self.client.force_login(tec)
        self.client.post(reverse("tecnico_aceptar", args=[sol.pk]))
        sol.refresh_from_db()
        self.assertEqual(sol.estado, "en_curso")

    def test_privada_no_sale_y_precio_editable(self):
        cli, tec, sol = self._flujo()
        self.client.force_login(cli)
        self.client.post(reverse("solicitud_precio", args=[sol.pk]),
                         {"precio_ofrecido": "65000", "visible_tecnicos": "on"})
        sol.refresh_from_db()
        self.assertEqual(sol.precio_ofrecido, 65000)
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_mapa"))
        self.assertContains(resp, "65.000")
        self.client.force_login(cli)
        self.client.post(reverse("solicitud_precio", args=[sol.pk]), {})
        sol.refresh_from_db()
        self.assertFalse(sol.visible_tecnicos)
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_mapa"))
        self.assertNotContains(resp, "Fuga de agua bajo el lavaplatos.")

    def test_monto_se_confirma_antes_de_pagar(self):
        cli, tec, sol = self._flujo()
        sol.tecnico = tec
        sol.estado = Solicitud.Estado.EN_CURSO
        sol.save()
        self.client.force_login(tec)
        self.client.post(reverse("tecnico_finalizar", args=[sol.pk]),
                         {"monto": "80000", "notas": ""})
        self.client.force_login(cli)
        resp = self.client.get(reverse("solicitud_pagar", args=[sol.pk]))
        self.assertEqual(resp.status_code, 302)  # bloqueado sin aceptar
        self.client.post(reverse("monto_decidir"),
                         {"solicitud_id": sol.pk, "accion": "aceptar_monto"})
        sol.refresh_from_db()
        self.assertTrue(sol.monto_aceptado)
        resp = self.client.post(reverse("solicitud_pagar", args=[sol.pk]),
                                {"medio": "efectivo", "resultado": "exito"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Pago.objects.filter(
            solicitud=sol, estado="exitoso").exists())
        self.assertEqual(
            Comision.objects.get(pago__solicitud=sol).monto_comision, 8000)

    def test_tecnicos_filtra_por_solicitud_elegida(self):
        cli = self._cliente()
        s1 = Solicitud.objects.create(
            cliente=cli, categoria="plomeria",
            descripcion="Fuga de agua bajo el lavaplatos.",
            direccion="Cra 13 #52-40", urgencia="normal")
        s2 = Solicitud.objects.create(
            cliente=cli, categoria="electricidad",
            descripcion="Corto en la sala que hace chispa.",
            direccion="Cra 13 #52-40", urgencia="normal")
        self.client.force_login(cli)
        resp = self.client.get(reverse("tecnicos") + f"?solicitud={s2.pk}")
        self.assertContains(resp, f"Para tu solicitud #{s2.pk}")
        self.assertContains(resp, f"?solicitud={s1.pk}")
        # Elegir dirige ESA solicitud, no la última.
        tec = self._tecnico("htec@test.co")
        self.client.get(reverse("tecnicos") + f"?solicitud={s1.pk}&elegir={tec.pk}")
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.tecnico_id, tec.pk)
        self.assertIsNone(s2.tecnico_id)

    def test_inicio_muestra_todas_las_activas(self):
        cli = self._cliente()
        for desc in ("Fuga uno en la cocina.", "Corto dos en la sala."):
            Solicitud.objects.create(
                cliente=cli, categoria="plomeria", descripcion=desc,
                direccion="Cra 13 #52-40", urgencia="normal")
        self.client.force_login(cli)
        resp = self.client.get(reverse("cliente_inicio"))
        self.assertContains(resp, "Fuga uno en la cocina.")
        self.assertContains(resp, "Corto dos en la sala.")

    def test_habilidad_aprobada_entra_al_matching(self):
        tec = self._tecnico("htec@test.co")
        doc = DocumentoTecnico.objects.create(
            perfil=tec.perfil_tecnico, nombre="Curso electricidad",
            especialidad="electricidad",
            archivo=_certificado("curso.pdf"))
        adm = self._usuario(Usuario.Rol.CLIENTE, "adm@test.co", staff=True)
        self.client.force_login(adm)
        self.client.post(reverse("documento_decidir"),
                         {"documento_id": doc.pk, "accion": "aprobar_doc"})
        self.assertIn("electricidad", tec.perfil_tecnico.especialidades_efectivas)
        cli = self._cliente()
        Solicitud.objects.create(
            cliente=cli, categoria="electricidad",
            descripcion="Corto en la sala que hace chispa.",
            direccion="Cra 13 #52-40", urgencia="normal")
        self.client.force_login(tec)
        resp = self.client.get(reverse("tecnico_solicitudes"))
        self.assertContains(resp, "Corto en la sala")

    def test_perfil_expone_coords_con_punto_para_el_mapa(self):
        """Regresión: es-co localiza con coma; el mapa JS necesita punto."""
        cli = self._cliente()
        cli.latitud = 4.679621
        cli.longitud = -74.08699
        cli.save(update_fields=["latitud", "longitud"])
        self.client.force_login(cli)
        resp = self.client.get(reverse("cliente_perfil"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-lat="4.679621"')
        self.assertContains(resp, 'data-lng="-74.08699"')
