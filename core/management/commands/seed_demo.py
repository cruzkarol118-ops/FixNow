"""F5 — datos demo idempotentes para la sustentación.

Uso:
    .\\.venv\\Scripts\\python.exe manage.py seed_demo
    .\\.venv\\Scripts\\python.exe manage.py seed_demo --help

Crea (borrando antes cualquier dato demo previo, por eso es idempotente):
    - 1 admin: admin@fixnow.co (staff + superuser)
    - 2 clientes demo (cliente1/cliente2@demo.fixnow.co)
    - 3 técnicos demo activos y disponibles, con perfil y coords de Bogotá
    - 3 solicitudes demo en distintos estados (pendiente, en_curso, finalizada)
    - 1 calificación (5★ sobre la finalizada)

Contraseña de TODOS: Demo123!
NO se corre contra fixnow_db salvo que quieras ensuciarla: para probar y
limpiar después, borra los usuarios demo desde /admin/ o con flush.
"""

from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Calificacion, Notificacion, Pago, PerfilTecnico, Solicitud, Usuario,
)

PASSWORD_DEMO = "Demo123!"

ADMIN_CORREO = "admin@fixnow.co"
CLIENTES = [
    ("cliente1@demo.fixnow.co", "Demo Cliente Uno", "70000001", "Cra 13 #52-40",
     4.6486, -74.0628),
    ("cliente2@demo.fixnow.co", "Demo Cliente Dos", "70000002", "Cl 63 #9-15",
     4.6560, -74.0590),
]
TECNICOS = [
    ("tecnico1@demo.fixnow.co", "Demo Tecnico Plomero", "70000011", "plomeria",
     60000, 4.6510, -74.0610),
    ("tecnico2@demo.fixnow.co", "Demo Tecnica Electrica", "70000012", "electricidad",
     55000, 4.6420, -74.0700),
    ("tecnico3@demo.fixnow.co", "Demo Tecnico Cerrajero", "70000013", "cerrajeria",
     50000, 4.6690, -74.0520),
]
CORREOS_DEMO = [ADMIN_CORREO] + [c[0] for c in CLIENTES] + [t[0] for t in TECNICOS]


class Command(BaseCommand):
    help = (
        "Carga datos demo idempotentes (admin@fixnow.co, 2 clientes, "
        "3 técnicos, 3 solicitudes, 1 calificación; clave Demo123!). "
        "Si ya existen, los borra y recrea."
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            self._borrar_previos()
            admin = self._crear_admin()
            clientes = [self._crear_cliente(*datos) for datos in CLIENTES]
            tecnicos = [self._crear_tecnico(*datos) for datos in TECNICOS]
            solicitudes = self._crear_solicitudes(clientes, tecnicos)
            self._crear_calificacion(solicitudes[2])
        self.stdout.write(self.style.SUCCESS(
            "Demo lista: admin@fixnow.co, cliente1/cliente2@demo.fixnow.co, "
            "tecnico1/2/3@demo.fixnow.co (clave Demo123! para todos). "
            f"Admin panel: {admin.correo}."
        ))

    # ---- limpieza previa (idempotencia) ----
    def _borrar_previos(self):
        demo = Usuario.objects.filter(correo__in=CORREOS_DEMO)
        # Pago protege a Solicitud: se borra primero (su Comision cae en cascada).
        Pago.objects.filter(
            solicitud__cliente__in=demo).delete()
        # Notificaciones y calificaciones caen en cascada con usuario/solicitud.
        Solicitud.objects.filter(cliente__in=demo).delete()
        Notificacion.objects.filter(usuario__in=demo).delete()
        demo.delete()

    # ---- creación ----
    def _crear_admin(self):
        return Usuario.objects.create_superuser(
            correo=ADMIN_CORREO, password=PASSWORD_DEMO,
            cedula="70000000", nombre_completo="Demo Admin",
            telefono="3000000000",
        )

    def _crear_cliente(self, correo, nombre, cedula, direccion, lat, lng):
        usuario = Usuario.objects.create_user(
            correo=correo, password=PASSWORD_DEMO, cedula=cedula,
            nombre_completo=nombre, telefono="3000000000",
            rol=Usuario.Rol.CLIENTE, estado=Usuario.Estado.ACTIVO,
            direccion=direccion, latitud=lat, longitud=lng,
        )
        return usuario

    def _crear_tecnico(self, correo, nombre, cedula, especialidad, precio, lat, lng):
        usuario = Usuario.objects.create_user(
            correo=correo, password=PASSWORD_DEMO, cedula=cedula,
            nombre_completo=nombre, telefono="3000000000",
            rol=Usuario.Rol.TECNICO, estado=Usuario.Estado.ACTIVO,
            direccion="Bogotá", latitud=lat, longitud=lng,
        )
        perfil = PerfilTecnico.objects.create(
            usuario=usuario, especialidad=especialidad, ciudad="Bogotá",
            precio_referencia=Decimal(precio), zona_cobertura="Bogotá",
            disponible=True,
        )
        perfil.documento_certificacion.save(
            "cert_demo.pdf", ContentFile(b"%PDF-1.4 demo"), save=True)
        return usuario

    def _crear_solicitudes(self, clientes, tecnicos):
        cli1, cli2 = clientes
        tec1, tec2, tec3 = tecnicos
        pendiente = Solicitud.objects.create(
            cliente=cli1, categoria="plomeria", urgencia=Solicitud.Urgencia.URGENTE,
            descripcion="Fuga de agua bajo el lavaplatos de la cocina.",
            direccion=cli1.direccion,
        )
        en_curso = Solicitud.objects.create(
            cliente=cli1, categoria="electricidad",
            descripcion="Tomacorriente de la sala hace chispa al conectar.",
            direccion=cli1.direccion,
        )
        en_curso.aceptar(tec2)
        finalizada = Solicitud.objects.create(
            cliente=cli2, categoria="cerrajeria",
            descripcion="Cambio de guardas de la puerta principal.",
            direccion=cli2.direccion,
        )
        finalizada.aceptar(tec3)
        finalizada.finalizar(notas="Guardas cambiadas y probadas.", monto_final=Decimal(80000))
        # tec1 queda disponible para que la demo de FN-4 lo liste.
        assert tec1.perfil_tecnico.disponible
        return [pendiente, en_curso, finalizada]

    def _crear_calificacion(self, solicitud):
        cal, _ = Calificacion.objects.get_or_create(
            solicitud=solicitud,
            defaults={"estrellas": 5,
                      "comentario": "Excelente trabajo, puntual y muy amable."},
        )
        return cal
