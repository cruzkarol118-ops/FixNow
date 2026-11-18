"""Carga un conjunto idempotente de datos para la demostración de FixNow.

Uso: ``python manage.py seed_demo``

Todos los usuarios demo usan la contraseña ``Clave123!``. El comando borra y
recrea únicamente las cuentas demo enumeradas aquí y sus datos asociados.
"""

import hashlib
import io
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from core.models import (
    Calificacion, Direccion, DocumentoTecnico, FotoSolicitud,
    IASugerencia, Notificacion, Pago, PerfilTecnico, Solicitud, Usuario,
)

PASSWORD_DEMO = "Clave123!"
ADMIN_CORREO = "admin@test.co"
SUSP_CORREO = "susp@test.co"

CLIENTES = [
    ("cliente1@test.co", "Demo Cliente Uno", "70000001", "Cra 13 #52-40", 4.6486, -74.0628),
    ("cliente2@test.co", "Demo Cliente Dos", "70000002", "Cl 63 #9-15", 4.6560, -74.0590),
    ("cliente3@test.co", "Valentina Gomez", "70000004", "Cl 85 #12-40, Chapinero", 4.6598, -74.0595),
    ("cliente4@test.co", "Mateo Restrepo", "70000005", "Cra 19 #93-56, Usaquen", 4.6958, -74.0305),
    ("cliente5@test.co", "Camila Pardo", "70000006", "Cl 170 #45-20, Suba", 4.7410, -74.0825),
    ("cliente6@test.co", "Sebastian Munoz", "70000007", "Cra 73 #10-45, Kennedy", 4.6305, -74.1505),
    ("cliente7@test.co", "Daniela Castro", "70000008", "Cl 26 #19-40, Teusaquillo", 4.6170, -74.0930),
    ("cliente8@test.co", "Juan Pablo Vargas", "70000101", "Cra 7 #63-25, Chapinero", 4.6480, -74.0630),
    ("cliente9@test.co", "Mariana Lopez", "70000102", "Cl 127 #18-45, Usaquen", 4.7040, -74.0470),
    ("cliente10@test.co", "David Ramirez", "70000103", "Cra 52 #128-30, Suba", 4.7350, -74.0720),
    ("cliente11@test.co", "Sara Rodriguez", "70000104", "Cl 45 #28-18, Teusaquillo", 4.6320, -74.0750),
    ("cliente12@test.co", "Nicolas Fernandez", "70000105", "Cra 68 #24-16, Salitre", 4.6530, -74.1100),
    ("cliente13@test.co", "Laura Jimenez", "70000106", "Cl 140 #15-60, Cedritos", 4.7180, -74.0390),
    ("cliente14@test.co", "Felipe Acosta", "70000107", "Cra 78 #8-35, Castilla", 4.6320, -74.1410),
    ("cliente15@test.co", "Andrea Salazar", "70000108", "Cl 72 #24-20, Barrios Unidos", 4.6610, -74.0750),
    ("cliente16@test.co", "Julian Herrera", "70000109", "Cra 3 #12-50, La Candelaria", 4.5970, -74.0710),
    ("cliente17@test.co", "Paula Cardenas", "70000110", "Cl 80 #96-22, Engativa", 4.7060, -74.1120),
    ("cliente18@test.co", "Andres Beltran", "70000111", "Cra 50 #26-35, Teusaquillo", 4.6320, -74.0920),
    ("cliente19@test.co", "Manuela Torres", "70000112", "Cl 116 #45-12, Pasadena", 4.6960, -74.0590),
    ("cliente20@test.co", "Santiago Rojas", "70000113", "Cra 80 #15-30, Modelia", 4.6650, -74.1200),
]

# correo, nombre, cédula, especialidad, precio, latitud, longitud, estado, disponible
TECNICOS = [
    ("tecnico1@test.co", "Demo Tecnico Plomero", "70000011", "plomeria", 60000, 4.6510, -74.0610, Usuario.Estado.ACTIVO, True),
    ("tecnico2@test.co", "Demo Tecnica Electrica", "70000012", "electricidad", 55000, 4.6420, -74.0700, Usuario.Estado.ACTIVO, True),
    ("tecnico3@test.co", "Demo Tecnico Cerrajero", "70000013", "cerrajeria", 50000, 4.6690, -74.0520, Usuario.Estado.ACTIVO, True),
    ("tecnico4@test.co", "Santiago Rojas", "70000014", "electrodomesticos", 58000, 4.6510, -74.0580, Usuario.Estado.ACTIVO, True),
    ("tecnico5@test.co", "Andres Cardenas", "70000015", "plomeria", 65000, 4.7120, -74.0450, Usuario.Estado.ACTIVO, True),
    ("tecnico6@test.co", "Laura Mendez", "70000016", "electricidad", 55000, 4.6990, -74.0310, Usuario.Estado.PENDIENTE_APROBACION, False),
    ("tecnico7@test.co", "Felipe Herrera", "70000017", "cerrajeria", 50000, 4.5965, -74.0745, Usuario.Estado.PENDIENTE_APROBACION, False),
    ("tecnico8@test.co", "Nicolas Torres", "70000018", "otro", 45000, 4.7180, -74.1150, Usuario.Estado.RECHAZADO, False),
    ("tecnico9@test.co", "Camilo Pineda", "70000119", "plomeria", 58000, 4.6500, -74.0640, Usuario.Estado.ACTIVO, True),
    ("tecnico10@test.co", "Diego Morales", "70000120", "plomeria", 62000, 4.6420, -74.0580, Usuario.Estado.ACTIVO, True),
    ("tecnico11@test.co", "Jorge Salcedo", "70000121", "plomeria", 55000, 4.6570, -74.0680, Usuario.Estado.ACTIVO, True),
    ("tecnico12@test.co", "Oscar Benavides", "70000122", "plomeria", 68000, 4.7060, -74.0430, Usuario.Estado.ACTIVO, True),
    ("tecnico13@test.co", "Ricardo Suarez", "70000123", "plomeria", 60000, 4.6970, -74.0370, Usuario.Estado.ACTIVO, True),
    ("tecnico14@test.co", "Mauricio Gil", "70000124", "plomeria", 52000, 4.7310, -74.0780, Usuario.Estado.ACTIVO, True),
    ("tecnico15@test.co", "Esteban Parra", "70000125", "plomeria", 57000, 4.6460, -74.0730, Usuario.Estado.ACTIVO, True),
    ("tecnico16@test.co", "Julian Buitrago", "70000126", "plomeria", 64000, 4.6350, -74.0830, Usuario.Estado.ACTIVO, True),
    ("tecnico17@test.co", "Fernando Cifuentes", "70000127", "plomeria", 59000, 4.6660, -74.1120, Usuario.Estado.ACTIVO, True),
    ("tecnico18@test.co", "Hernan Duarte", "70000128", "plomeria", 56000, 4.6610, -74.0600, Usuario.Estado.ACTIVO, True),
    ("tecnico19@test.co", "Paola Vargas", "70000129", "electricidad", 62000, 4.6550, -74.0610, Usuario.Estado.ACTIVO, True),
    ("tecnico20@test.co", "Miguel Angel Ruiz", "70000130", "electricidad", 60000, 4.6920, -74.0490, Usuario.Estado.ACTIVO, True),
    ("tecnico21@test.co", "Cristian Ospina", "70000131", "cerrajeria", 52000, 4.6470, -74.0710, Usuario.Estado.ACTIVO, True),
    ("tecnico22@test.co", "Diana Marcela Leon", "70000132", "cerrajeria", 55000, 4.6750, -74.0580, Usuario.Estado.ACTIVO, True),
    ("tecnico23@test.co", "Angela Parra", "70000133", "electrodomesticos", 65000, 4.6590, -74.0670, Usuario.Estado.ACTIVO, True),
    ("tecnico24@test.co", "Roberto Marin", "70000134", "electrodomesticos", 70000, 4.7000, -74.0410, Usuario.Estado.ACTIVO, True),
]

CORREOS_LEGACY = [
    "admin@fixnow.co", "cliente1@demo.fixnow.co", "cliente2@demo.fixnow.co",
    "tecnico1@demo.fixnow.co", "tecnico2@demo.fixnow.co", "tecnico3@demo.fixnow.co",
]
CORREOS_DEMO = [ADMIN_CORREO, SUSP_CORREO] + [row[0] for row in CLIENTES + TECNICOS]


class Command(BaseCommand):
    help = "Recrea el entorno poblado de demo: clientes, técnicos cercanos, solicitudes y actividad. Clave: Clave123!."

    def handle(self, *args, **options):
        with transaction.atomic():
            self._borrar_previos()
            admin = self._crear_admin()
            suspendido = self._crear_suspendido()
            clientes = [self._crear_cliente(*datos) for datos in CLIENTES]
            tecnicos = [self._crear_tecnico(*datos, dias=70 - i * 2) for i, datos in enumerate(TECNICOS)]
            solicitudes = self._crear_solicitudes(clientes, tecnicos)
            calificaciones = self._crear_calificaciones(solicitudes)
            pagos = self._crear_pagos(solicitudes)
            self._crear_direcciones(clientes)
            self._crear_documentos(tecnicos)
            self._crear_fotos(solicitudes)
            self._crear_ia()
            self._crear_notificaciones(admin, suspendido, clientes, tecnicos, solicitudes, calificaciones, pagos)

        self.stdout.write(self.style.SUCCESS(
            "Demo lista: 20 clientes, 24 técnicos (21 activos, 12 plomeros), "
            "susp@test.co. Contraseña para todos: Clave123!. "
            f"Solicitudes: {len(solicitudes)}; reseñas: {len(calificaciones)}; pagos: {len(pagos)}."
        ))

    def _borrar_previos(self):
        demo = Usuario.objects.filter(correo__in=CORREOS_DEMO + CORREOS_LEGACY)
        Pago.objects.filter(solicitud__cliente__in=demo).delete()
        Solicitud.objects.filter(cliente__in=demo).delete()
        Notificacion.objects.filter(usuario__in=demo).delete()
        demo.delete()
        IASugerencia.objects.filter(origen="seed_demo").delete()

    @staticmethod
    def _fecha(objeto, campo, dias):
        valor = timezone.now() - timedelta(days=dias)
        objeto.__class__.objects.filter(pk=objeto.pk).update(**{campo: valor})
        setattr(objeto, campo, valor)

    def _crear_admin(self):
        admin = Usuario.objects.create_superuser(
            correo=ADMIN_CORREO, password=PASSWORD_DEMO, cedula="70000000",
            nombre_completo="Demo Admin", telefono="3000000000")
        self._fecha(admin, "date_joined", 70)
        return admin

    def _crear_suspendido(self):
        user = Usuario.objects.create_user(
            correo=SUSP_CORREO, password=PASSWORD_DEMO, cedula="70000003",
            nombre_completo="Demo Suspendido", telefono="3000000000",
            rol=Usuario.Rol.CLIENTE, direccion="Cra 13 #52-40, Bogotá")
        user.suspender("Cuenta suspendida para la demo (probar bloqueo).")
        self._fecha(user, "date_joined", 60)
        return user

    def _crear_cliente(self, correo, nombre, cedula, direccion, lat, lng):
        user = Usuario.objects.create_user(
            correo=correo, password=PASSWORD_DEMO, cedula=cedula,
            nombre_completo=nombre, telefono="3000000000",
            rol=Usuario.Rol.CLIENTE, estado=Usuario.Estado.ACTIVO,
            direccion=direccion, latitud=lat, longitud=lng)
        numero = int(correo.split("cliente")[1].split("@")[0])
        self._fecha(user, "date_joined", max(2, 49 - numero * 5))
        return user

    def _crear_tecnico(self, correo, nombre, cedula, especialidad, precio, lat, lng, estado, disponible, dias):
        user = Usuario.objects.create_user(
            correo=correo, password=PASSWORD_DEMO, cedula=cedula,
            nombre_completo=nombre, telefono="3000000000",
            rol=Usuario.Rol.TECNICO, estado=estado, direccion="Bogotá",
            latitud=lat, longitud=lng)
        perfil = PerfilTecnico.objects.create(
            usuario=user, especialidad=especialidad, ciudad="Bogotá",
            precio_referencia=Decimal(precio), zona_cobertura="Bogotá",
            disponible=disponible)
        perfil.documento_certificacion.save(
            f"cert_{correo.split('@')[0]}.pdf",
            ContentFile(self._pdf_demo(nombre)), save=True)
        self._fecha(user, "date_joined", dias)
        if correo.startswith("tecnico7"):
            user.motivo_rechazo = "Te falta adjuntar el certificado de experiencia."
            user.save(update_fields=["motivo_rechazo"])
        elif correo.startswith("tecnico8"):
            user.motivo_rechazo = "Documento ilegible; vuelve a subirlo."
            user.save(update_fields=["motivo_rechazo"])
        return user

    @staticmethod
    def _pdf_demo(nombre):
        """PDF mínimo válido y claramente marcado como material de demostración."""
        nombre_ascii = nombre.encode("ascii", "ignore").decode("ascii")
        lineas = [
            "FIXNOW - CERTIFICADO DE DEMOSTRACION",
            "DOCUMENTO FICTICIO - NO ES UNA CERTIFICACION REAL",
            f"Tecnico: {nombre_ascii}",
        ]
        comandos = ["BT", "/F1 16 Tf", "72 720 Td"]
        for indice, linea in enumerate(lineas):
            texto = linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if indice:
                comandos.append("0 -32 Td")
                comandos.append("/F1 12 Tf")
            comandos.append(f"({texto}) Tj")
        comandos.append("ET")
        contenido = "\n".join(comandos).encode("ascii")
        objetos = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(contenido)).encode("ascii") + b" >>\nstream\n" + contenido + b"\nendstream",
        ]
        pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for numero, objeto in enumerate(objetos, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{numero} 0 obj\n".encode("ascii"))
            pdf.extend(objeto)
            pdf.extend(b"\nendobj\n")
        xref = len(pdf)
        pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n".encode("ascii"))
        return bytes(pdf)

    def _solicitud(self, cliente, tecnico, categoria, descripcion, dias, estado,
                   monto=None, urgencia=Solicitud.Urgencia.NORMAL, **extras):
        solicitud = Solicitud.objects.create(
            cliente=cliente, categoria=categoria, descripcion=descripcion,
            direccion=cliente.direccion, urgencia=urgencia, **extras)
        self._fecha(solicitud, "fecha_creacion", dias)
        if tecnico:
            solicitud.aceptar(tecnico)
            self._fecha(solicitud, "fecha_asignacion", max(0, dias - 1))
        if estado == Solicitud.Estado.FINALIZADA:
            solicitud.finalizar(notas="Trabajo realizado y probado.", monto_final=Decimal(monto))
            self._fecha(solicitud, "fecha_finalizacion", max(0, dias - 2))
        elif estado == Solicitud.Estado.CANCELADA:
            solicitud.cancelar()
        return solicitud

    def _crear_solicitudes(self, c, t):
        resultado = []
        # 6 finalizadas con edades variadas.
        resultado.append(self._solicitud(c[2], t[0], "plomeria", "Reparación de fuga en llave de paso.", 38, Solicitud.Estado.FINALIZADA, 120000))
        resultado.append(self._solicitud(c[3], t[1], "electricidad", "Instalación de dos tomas nuevas en el estudio.", 31, Solicitud.Estado.FINALIZADA, 95000))
        resultado.append(self._solicitud(c[1], t[2], "cerrajeria", "Cambio de guardas de la puerta principal.", 24, Solicitud.Estado.FINALIZADA, 80000))
        resultado.append(self._solicitud(c[6], t[3], "electrodomesticos", "Lavadora no centrifuga y el motor hace ruido.", 45, Solicitud.Estado.FINALIZADA, 200000))
        resultado.append(self._solicitud(c[4], t[3], "electrodomesticos", "Nevera no enfría la parte inferior.", 17, Solicitud.Estado.FINALIZADA, 150000))
        resultado.append(self._solicitud(c[5], t[4], "plomeria", "Destapar sifón de cocina y revisar las llaves.", 11, Solicitud.Estado.FINALIZADA, 70000))
        # Pendientes y en curso.
        resultado.append(self._solicitud(c[0], None, "plomeria", "Fuga de agua bajo el lavaplatos de la cocina.", 1, Solicitud.Estado.PENDIENTE, urgencia=Solicitud.Urgencia.URGENTE))
        resultado.append(self._solicitud(c[0], t[1], "electricidad", "Tomacorriente de la sala hace chispa al conectar.", 4, Solicitud.Estado.EN_CURSO))
        resultado.append(self._solicitud(c[6], t[2], "cerrajeria", "Puerta del apartamento atascada al mediodía.", 2, Solicitud.Estado.EN_CURSO))
        resultado.append(self._solicitud(c[2], None, "cerrajeria", "Perdí las llaves y necesito abrir la puerta.", 3, Solicitud.Estado.PENDIENTE, precio_ofrecido=Decimal("60000")))
        resultado.append(self._solicitud(c[3], None, "electrodomesticos", "La licuadora hace un ruido extraño al encender.", 6, Solicitud.Estado.PENDIENTE, visible_tecnicos=False))
        # Pendiente dirigida a tecnico4 para el flujo privado del marketplace.
        resultado[-1].tecnico = t[3]
        resultado[-1].save(update_fields=["tecnico"])
        resultado.append(self._solicitud(c[5], None, "electricidad", "Chispas ocasionales en el tablero eléctrico.", 0, Solicitud.Estado.PENDIENTE, urgencia=Solicitud.Urgencia.URGENTE))
        resultado.append(self._solicitud(c[4], None, "plomeria", "Goteo lento bajo el lavamanos del baño.", 20, Solicitud.Estado.CANCELADA))
        resultado.append(self._solicitud(c[1], None, "electrodomesticos", "Microondas no enciende; lo reparé por cuenta propia.", 33, Solicitud.Estado.CANCELADA))

        # Actividad adicional distribuida entre barrios, clientes y especialidades.
        activas_por_categoria = {}
        for tecnico in t:
            if tecnico.estado == Usuario.Estado.ACTIVO and tecnico.perfil_tecnico.disponible:
                activas_por_categoria.setdefault(tecnico.perfil_tecnico.especialidad, []).append(tecnico)
        categorias = ["plomeria", "electricidad", "cerrajeria", "electrodomesticos"]
        descripciones = {
            "plomeria": [
                "La llave del lavaplatos gotea y necesito cambiar el empaque.",
                "El sifon del lavamanos esta drenando muy lento.",
                "Hay humedad alrededor de la tuberia de la cocina.",
                "Necesito instalar una ducha nueva en el apartamento.",
                "El sanitario pierde agua despues de descargar.",
            ],
            "electricidad": [
                "La luz de la cocina parpadea desde esta manana.",
                "Quiero instalar una lampara en el estudio.",
                "Un interruptor se calienta cuando lo usamos.",
                "Necesito revisar el breaker de la zona de ropas.",
                "Dos tomacorrientes dejaron de funcionar en la sala.",
            ],
            "cerrajeria": [
                "La cerradura de la puerta principal se atasca al girar.",
                "Necesito cambiar la chapa del apartamento por seguridad.",
                "La llave se quedo dura y no abre bien la puerta.",
                "Quiero instalar una cerradura nueva en la oficina.",
                "La puerta del garaje no asegura correctamente.",
            ],
            "electrodomesticos": [
                "La lavadora llena pero no empieza el ciclo de lavado.",
                "La nevera hace ruido y enfria menos que antes.",
                "La estufa electrica no calienta una de las hornillas.",
                "La secadora termina el ciclo pero deja la ropa humeda.",
                "El horno no mantiene la temperatura seleccionada.",
            ],
        }
        self.solicitudes_finalizadas_extra = []
        self.solicitudes_en_curso_extra = []
        self.solicitudes_pendientes_extra = []
        self.solicitudes_canceladas_extra = []

        for i in range(20):
            categoria = categorias[i % len(categorias)]
            opciones = activas_por_categoria[categoria]
            tecnico = opciones[(i // len(categorias)) % len(opciones)]
            cliente = c[(i * 3 + 2) % len(c)]
            dias = 10 + ((i * 7) % 43)
            monto = 48000 + (i % 8) * 12500
            solicitud = self._solicitud(
                cliente, tecnico, categoria,
                descripciones[categoria][i % len(descripciones[categoria])],
                dias, Solicitud.Estado.FINALIZADA, monto,
            )
            self.solicitudes_finalizadas_extra.append(solicitud)
            resultado.append(solicitud)

        for i in range(8):
            categoria = categorias[(i + 1) % len(categorias)]
            opciones = activas_por_categoria[categoria]
            tecnico = opciones[i % len(opciones)]
            cliente = c[(i * 2 + 1) % len(c)]
            solicitud = self._solicitud(
                cliente, tecnico, categoria,
                descripciones[categoria][(i + 2) % len(descripciones[categoria])],
                1 + i % 7, Solicitud.Estado.EN_CURSO,
            )
            self.solicitudes_en_curso_extra.append(solicitud)
            resultado.append(solicitud)

        categorias_pendientes = ["plomeria", "plomeria", "electricidad", "plomeria", "cerrajeria", "electrodomesticos"]
        for i in range(18):
            categoria = categorias_pendientes[i % len(categorias_pendientes)]
            cliente = c[(i * 5 + 1) % len(c)]
            solicitud = self._solicitud(
                cliente, None, categoria,
                descripciones[categoria][(i + 1) % len(descripciones[categoria])],
                2 + i % 17, Solicitud.Estado.PENDIENTE,
                urgencia=(Solicitud.Urgencia.URGENTE if i in (3, 10, 16) else Solicitud.Urgencia.NORMAL),
                precio_ofrecido=(Decimal(55000 + i * 1500) if i % 4 == 0 else None),
            )
            self.solicitudes_pendientes_extra.append(solicitud)
            resultado.append(solicitud)

        for i in range(5):
            categoria = categorias[i % len(categorias)]
            cliente = c[(i * 4 + 3) % len(c)]
            solicitud = self._solicitud(
                cliente, None, categoria,
                descripciones[categoria][(i + 3) % len(descripciones[categoria])],
                12 + i * 3, Solicitud.Estado.CANCELADA,
            )
            self.solicitudes_canceladas_extra.append(solicitud)
            resultado.append(solicitud)
        return resultado

    def _crear_calificaciones(self, solicitudes):
        datos = [
            (0, 5, "Muy profesional, llegó puntual y dejó todo limpio.", False, False),
            (1, 4, "Buen trabajo, aunque tardó un poco más de lo acordado.", False, False),
            (2, 5, "Excelente trabajo, puntual y muy amable.", False, False),
            (3, 2, "Volvió a fallar a la semana; no lo recomiendo.", True, False),
            (4, 3, "Cobró de más por el diagnóstico y fue descortés.", False, True),
        ]
        resenas = []
        for indice, estrellas, comentario, oculta, revision in datos:
            cal = Calificacion.objects.create(
                solicitud=solicitudes[indice], estrellas=estrellas,
                comentario=comentario, oculta=oculta, revision_admin=revision)
            self._fecha(cal, "fecha_creacion", max(1, [35, 28, 21, 40, 14][indice]))
            resenas.append(cal)
        comentarios = [
            (5, "Llego puntual, explico el problema y dejo todo funcionando."),
            (4, "Buen servicio y precio razonable. Volveria a contactarlo."),
            (5, "Muy amable y cuidadoso con el apartamento."),
            (4, "Resolvió la falla en una sola visita, recomendado."),
            (3, "El trabajo quedo bien, aunque tuvo que volver por una pieza."),
            (5, "Excelente comunicacion desde que acepto la solicitud."),
            (4, "Dejo el area limpia y cumplio con lo acordado."),
            (2, "La reparacion duro menos de lo esperado; quedamos en revisar."),
            (5, "Identifico rapido la fuga y cambio la pieza necesaria."),
            (4, "Servicio profesional, llego dentro del horario acordado."),
            (5, "Quedo muy bien la instalacion electrica, gracias."),
            (3, "Soluciono el problema pero se demoro mas de lo previsto."),
            (5, "La cerradura funciona perfecto y me dio recomendaciones."),
            (4, "Buen trabajo, claro con el costo antes de empezar."),
            (5, "Recomendado para mantenimiento de electrodomesticos."),
            (4, "Atento y ordenado. El equipo volvio a funcionar."),
            (3, "Cumplio con la reparacion; la comunicacion pudo ser mejor."),
            (5, "Muy buena experiencia, seguro lo vuelvo a llamar."),
        ]
        for i, solicitud in enumerate(self.solicitudes_finalizadas_extra):
            if i in (5, 13):
                continue  # Deja algunas finalizadas listas para que el usuario las califique.
            estrellas, comentario = comentarios[i % len(comentarios)]
            cal = Calificacion.objects.create(
                solicitud=solicitud, estrellas=estrellas, comentario=comentario,
                revision_admin=(i == 7), oculta=(i == 11),
            )
            self._fecha(cal, "fecha_creacion", max(1, (10 + (i * 7) % 43) - 2))
            resenas.append(cal)
        return resenas

    def _crear_pagos(self, solicitudes):
        pagos = []
        for i, (solicitud, medio, monto) in enumerate(zip(
                solicitudes[:5], [Pago.Medio.PSE, Pago.Medio.TARJETA, Pago.Medio.BILLETERA, Pago.Medio.PSE, Pago.Medio.TARJETA],
                [120000, 95000, 80000, 200000, 150000]), 1):
            solicitud.confirmar_monto()
            pago = Pago.objects.create(solicitud=solicitud, medio_pago=medio, monto=Decimal(monto))
            pago.marcar_exitoso(f"sandbox_demo_{i:04d}")
            self._fecha(pago, "fecha_creacion", [38, 31, 24, 45, 17][i - 1])
            self._fecha(pago.comision, "fecha_calculo", [38, 31, 24, 45, 17][i - 1])
            pagos.append(pago)
        solicitud = solicitudes[5]
        solicitud.confirmar_monto()
        pago = Pago.objects.create(solicitud=solicitud, medio_pago=Pago.Medio.TARJETA, monto=Decimal("70000"))
        pago.marcar_fallido("Tarjeta rechazada por el banco (sandbox).")
        self._fecha(pago, "fecha_creacion", 11)
        pagos.append(pago)

        for i, solicitud in enumerate(self.solicitudes_finalizadas_extra):
            if i in (5, 13, 19):
                continue  # Algunas finalizadas quedan listas para una accion en vivo.
            solicitud.confirmar_monto()
            pago = Pago.objects.create(
                solicitud=solicitud,
                medio_pago=[Pago.Medio.PSE, Pago.Medio.TARJETA, Pago.Medio.BILLETERA, Pago.Medio.EFECTIVO][i % 4],
                monto=solicitud.monto_final,
            )
            if i in (4, 14):
                pago.marcar_fallido("Transaccion de demostracion rechazada; puedes reintentar.")
            elif i in (8, 17):
                # Mantiene dos pagos pendientes visibles en el historial.
                pass
            else:
                pago.marcar_exitoso(f"sandbox_demo_extra_{i + 1:03d}")
                self._fecha(pago.comision, "fecha_calculo", max(1, 10 + (i * 7) % 43))
            self._fecha(pago, "fecha_creacion", max(1, 10 + (i * 7) % 43))
            pagos.append(pago)
        return pagos

    def _crear_direcciones(self, clientes):
        c1 = clientes[0]
        Direccion.objects.create(cliente=c1, etiqueta="Casa", direccion="Cra 13 #52-40, Chapinero, Bogotá", latitud=4.6486, longitud=-74.0628, es_principal=True)
        Direccion.objects.create(cliente=c1, etiqueta="Oficina", direccion="Cl 72 #10-34, Chapinero, Bogotá", latitud=4.6580, longitud=-74.0580)
        c4 = clientes[3]
        Direccion.objects.create(cliente=c4, etiqueta="Oficina", direccion="Cra 19 #93-56, Usaquén, Bogotá", latitud=4.6958, longitud=-74.0305)

    def _crear_documentos(self, tecnicos):
        documentos = [
            (tecnicos[3], "Curso de instalación y mantenimiento de aires acondicionados", "otro", DocumentoTecnico.Estado.APROBADO),
            (tecnicos[5], "Diplomado en redes y tableros industriales", "electricidad", DocumentoTecnico.Estado.PENDIENTE),
            (tecnicos[8], "Instalacion de calentadores y redes de agua", "plomeria", DocumentoTecnico.Estado.APROBADO),
            (tecnicos[18], "Mantenimiento de redes electricas residenciales", "electricidad", DocumentoTecnico.Estado.APROBADO),
            (tecnicos[20], "Apertura segura y cambio de cerraduras", "cerrajeria", DocumentoTecnico.Estado.PENDIENTE),
            (tecnicos[22], "Reparacion y mantenimiento de neveras", "electrodomesticos", DocumentoTecnico.Estado.APROBADO),
        ]
        for tecnico, nombre, especialidad, estado in documentos:
            doc = DocumentoTecnico.objects.create(
                perfil=tecnico.perfil_tecnico, nombre=nombre, especialidad=especialidad,
                estado=estado, archivo=ContentFile(
                    self._pdf_demo(nombre), name=f"doc_{tecnico.pk}.pdf"))
            self._fecha(doc, "fecha_subida", 8)

    @staticmethod
    def _imagen_demo(tipo):
        imagen = Image.new("RGB", (640, 420), "#f3f7f8")
        dibujo = ImageDraw.Draw(imagen)
        dibujo.rounded_rectangle((35, 35, 605, 385), radius=28, fill="#ffffff", outline="#cbd5e1", width=4)
        azul, oscuro = "#38bdf8", "#0f172a"
        if tipo == "plomeria":
            dibujo.ellipse((265, 95, 375, 225), fill=azul, outline=oscuro, width=5)
            dibujo.polygon([(320, 55), (265, 145), (375, 145)], fill=azul, outline=oscuro)
            dibujo.arc((210, 190, 430, 320), 180, 360, fill=oscuro, width=18)
            dibujo.line((230, 255, 410, 255), fill=oscuro, width=18)
        elif tipo == "electricidad":
            dibujo.rounded_rectangle((220, 90, 420, 310), radius=24, fill="#e2e8f0", outline=oscuro, width=6)
            dibujo.line((275, 145, 275, 205), fill=oscuro, width=14)
            dibujo.line((365, 145, 365, 205), fill=oscuro, width=14)
            dibujo.arc((285, 170, 355, 260), 0, 180, fill="#f59e0b", width=14)
        else:
            dibujo.rounded_rectangle((210, 160, 430, 270), radius=50, fill="#fbbf24", outline=oscuro, width=6)
            dibujo.ellipse((185, 175, 260, 250), fill="#f3f7f8", outline=oscuro, width=6)
            dibujo.line((395, 215, 470, 215), fill=oscuro, width=14)
            dibujo.line((445, 215, 445, 255), fill=oscuro, width=12)
        salida = io.BytesIO()
        imagen.save(salida, format="JPEG", quality=88)
        return salida.getvalue()

    def _crear_fotos(self, solicitudes):
        fotos = [
            (solicitudes[6], "plomeria", FotoSolicitud.Tipo.EVIDENCIA),
            (solicitudes[2], "cerrajeria", FotoSolicitud.Tipo.FINALIZACION),
        ]
        for i, solicitud in enumerate(self.solicitudes_finalizadas_extra):
            if i % 3 == 0:
                fotos.append((solicitud, solicitud.categoria, FotoSolicitud.Tipo.FINALIZACION))
        for i, solicitud in enumerate(self.solicitudes_pendientes_extra):
            if i % 4 == 0:
                fotos.append((solicitud, solicitud.categoria, FotoSolicitud.Tipo.EVIDENCIA))
        for solicitud, categoria, etiqueta in fotos:
            tipo = categoria if categoria in {"plomeria", "electricidad", "cerrajeria"} else "otro"
            foto = FotoSolicitud(solicitud=solicitud, tipo=etiqueta)
            foto.imagen.save(f"demo_{tipo}_{solicitud.pk}.jpg", ContentFile(self._imagen_demo(tipo)), save=True)

    def _crear_ia(self):
        muestras = [
            ("tengo una fuga en el lavaplatos", "plomeria", "plomeria", .93),
            ("el tomacorriente de la sala hace chispa", "electricidad", "electricidad", .89),
            ("necesito cambiar las guardas de la puerta", "cerrajeria", "cerrajeria", .87),
            ("la lavadora no centrifuga", "electrodomesticos", "electrodomesticos", .91),
            ("la nevera no enfria abajo", "electrodomesticos", "electrodomesticos", .83),
            ("destapar el sifon de la cocina", "plomeria", "plomeria", .79),
            ("chispa en el tablero por una fuga", "electricidad", "plomeria", .54),
            ("se atasco la puerta y la llave", "cerrajeria", "otro", .42),
            ("el lavamanos pierde agua por debajo", "plomeria", "plomeria", .86),
            ("quiero instalar una ducha en el bano", "plomeria", "plomeria", .82),
            ("la luz del comedor parpadea", "electricidad", "electricidad", .88),
            ("necesito cambiar la chapa de la oficina", "cerrajeria", "cerrajeria", .90),
            ("la secadora deja la ropa humeda", "electrodomesticos", "electrodomesticos", .85),
            ("el sanitario sigue llenando el tanque", "plomeria", "plomeria", .92),
            ("breaker se baja cuando prendo el horno", "electricidad", "electricidad", .78),
            ("la puerta del garaje no asegura", "cerrajeria", "cerrajeria", .81),
            ("la nevera hace ruido por la noche", "electrodomesticos", "electrodomesticos", .88),
            ("gotea la llave de paso del patio", "plomeria", "plomeria", .91),
            ("toma corriente de la habitacion no sirve", "electricidad", "electricidad", .84),
            ("perdi la llave del apartamento", "cerrajeria", "cerrajeria", .93),
            ("el horno no calienta parejo", "electrodomesticos", "electrodomesticos", .77),
        ]
        for texto, sugerida, final, confianza in muestras:
            IASugerencia.objects.create(
                texto_hash=hashlib.sha256(f"seed_demo|{texto}".encode()).hexdigest(),
                texto_muestra=texto, categoria_sugerida=sugerida,
                categoria_final=final, acierto=sugerida == final,
                confianza=confianza, origen="seed_demo")

    def _crear_notificaciones(self, admin, suspendido, clientes, tecnicos, solicitudes, calificaciones, pagos):
        notificaciones = [
            (clientes[2], Notificacion.Tipo.SOLICITUD_CREADA, "Recibimos tu solicitud de plomería.", solicitudes[0], True, 38),
            (clientes[2], Notificacion.Tipo.SOLICITUD_FINALIZADA, "Tu servicio fue finalizado.", solicitudes[0], True, 36),
            (clientes[2], Notificacion.Tipo.PAGO_EXITOSO, "Pago procesado correctamente.", solicitudes[0], True, 36),
            (clientes[3], Notificacion.Tipo.SOLICITUD_CREADA, "Recibimos tu solicitud de electricidad.", solicitudes[1], True, 31),
            (clientes[3], Notificacion.Tipo.SOLICITUD_FINALIZADA, "Tu servicio fue finalizado.", solicitudes[1], True, 29),
            (clientes[0], Notificacion.Tipo.SOLICITUD_CREADA, "Tu solicitud urgente fue publicada.", solicitudes[6], False, 1),
            (clientes[0], Notificacion.Tipo.SOLICITUD_ACEPTADA, "Un técnico aceptó tu solicitud.", solicitudes[7], True, 3),
            (clientes[5], Notificacion.Tipo.PAGO_FALLIDO, "El pago no se completó; puedes intentarlo de nuevo.", solicitudes[5], False, 10),
            (clientes[1], Notificacion.Tipo.SOLICITUD_FINALIZADA, "Tu servicio de cerrajería fue finalizado.", solicitudes[2], True, 22),
            (tecnicos[0], Notificacion.Tipo.CALIFICACION_RECIBIDA, "Recibiste una nueva calificación de 5 estrellas.", solicitudes[0], True, 35),
            (tecnicos[1], Notificacion.Tipo.CALIFICACION_RECIBIDA, "Recibiste una nueva calificación de 4 estrellas.", solicitudes[1], True, 28),
            (tecnicos[2], Notificacion.Tipo.CALIFICACION_RECIBIDA, "Recibiste una nueva calificación de 5 estrellas.", solicitudes[2], True, 21),
            (tecnicos[3], Notificacion.Tipo.CALIFICACION_RECIBIDA, "Recibiste una calificación que requiere revisión.", solicitudes[3], False, 14),
            (tecnicos[1], Notificacion.Tipo.SOLICITUD_ACEPTADA, "Aceptaste una solicitud de electricidad.", solicitudes[7], True, 3),
            (tecnicos[6], Notificacion.Tipo.INFO_SOLICITADA, "El administrador solicita el certificado de experiencia.", None, False, 2),
            (tecnicos[7], Notificacion.Tipo.TECNICO_RECHAZADO, "Tu registro fue rechazado: documento ilegible.", None, True, 9),
            (admin, Notificacion.Tipo.CALIFICACION_ALERTA, "Una calificación de 3 estrellas requiere revisión.", solicitudes[4], False, 14),
            (tecnicos[5], Notificacion.Tipo.TECNICO_APROBADO, "Tu registro está pendiente de revisión.", None, False, 4),
            (suspendido, Notificacion.Tipo.USUARIO_SUSPENDIDO, "Tu cuenta fue suspendida para la demostración.", None, True, 60),
        ]
        for usuario, tipo, mensaje, solicitud, leida, dias in notificaciones:
            notificacion = Notificacion.objects.create(
                usuario=usuario, tipo=tipo, mensaje=mensaje,
                solicitud=solicitud, leida=leida)
            self._fecha(notificacion, "fecha_creacion", dias)

        def avisar(usuario, tipo, mensaje, solicitud, fecha, leida):
            aviso = Notificacion.objects.create(
                usuario=usuario, tipo=tipo, mensaje=mensaje[:255],
                solicitud=solicitud, leida=leida)
            dias = max(0, (timezone.now() - fecha).days)
            self._fecha(aviso, "fecha_creacion", dias)

        for indice, solicitud in enumerate(solicitudes[14:]):
            edad = solicitud.fecha_creacion
            avisar(
                solicitud.cliente, Notificacion.Tipo.SOLICITUD_CREADA,
                f"Recibimos tu solicitud de {solicitud.get_categoria_display().lower()}.",
                solicitud, edad, indice % 4 != 0,
            )
            if solicitud.tecnico_id:
                fecha_asignacion = solicitud.fecha_asignacion or edad
                avisar(
                    solicitud.cliente, Notificacion.Tipo.SOLICITUD_ACEPTADA,
                    f"{solicitud.tecnico.nombre_completo} acepto tu solicitud.",
                    solicitud, fecha_asignacion, indice % 3 != 0,
                )
                avisar(
                    solicitud.tecnico, Notificacion.Tipo.SOLICITUD_ACEPTADA,
                    f"Aceptaste una solicitud de {solicitud.get_categoria_display().lower()}.",
                    solicitud, fecha_asignacion, indice % 2 == 0,
                )
            if solicitud.estado == Solicitud.Estado.FINALIZADA:
                avisar(
                    solicitud.cliente, Notificacion.Tipo.SOLICITUD_FINALIZADA,
                    "Tu servicio fue finalizado. Puedes revisar el detalle y calificarlo.",
                    solicitud, solicitud.fecha_finalizacion or edad, indice % 3 != 0,
                )

        solicitudes_extra_ids = {s.pk for s in self.solicitudes_finalizadas_extra}
        for cal in calificaciones:
            if cal.solicitud_id not in solicitudes_extra_ids:
                continue
            avisar(
                cal.solicitud.tecnico, Notificacion.Tipo.CALIFICACION_RECIBIDA,
                f"{cal.estrellas} estrellas: {cal.comentario}",
                cal.solicitud, cal.fecha_creacion, cal.pk % 2 == 0,
            )
            if cal.revision_admin:
                avisar(
                    admin, Notificacion.Tipo.CALIFICACION_ALERTA,
                    f"Resena de {cal.estrellas} estrellas pendiente de revision.",
                    cal.solicitud, cal.fecha_creacion, False,
                )

        for pago in pagos[6:]:
            if pago.estado == Pago.Estado.EXITOSO:
                tipo = Notificacion.Tipo.PAGO_EXITOSO
                mensaje = "El pago del servicio se proceso correctamente."
            elif pago.estado == Pago.Estado.FALLIDO:
                tipo = Notificacion.Tipo.PAGO_FALLIDO
                mensaje = "El pago no se completo; puedes intentarlo nuevamente."
            else:
                continue
            avisar(
                pago.solicitud.cliente, tipo, mensaje, pago.solicitud,
                pago.fecha_creacion, pago.estado == Pago.Estado.EXITOSO,
            )
