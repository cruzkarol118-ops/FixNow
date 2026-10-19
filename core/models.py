"""
Modelos de FixNow.

Un solo lugar para todo el esquema, pensado para que las 20 historias
(FN-1 a FN-20) no necesiten cambios de estructura más adelante.
Cada campo tiene un comentario con la historia que lo pide, para que
puedan revisar contra el documento de sprints.

Categorías, estados y roles están centralizados en clases *Choices*
para no repetir strings sueltos por el código (y para que coincidan
exactamente con los valores que ya usa el frontend en
frontend/datos_falsos.py).
"""
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .validators import (
    validar_cedula, validar_certificacion, validar_foto, validar_nombre,
    validar_telefono,
)


# =====================================================================
# Catálogos compartidos
# =====================================================================

class Categoria(models.TextChoices):
    """Mismos ids que frontend/datos_falsos.py, para no duplicar el catálogo."""
    PLOMERIA = "plomeria", "Plomería"
    ELECTRICIDAD = "electricidad", "Electricidad"
    CERRAJERIA = "cerrajeria", "Cerrajería"
    ELECTRODOMESTICOS = "electrodomesticos", "Electrodomésticos"
    OTRO = "otro", "Otro"


# =====================================================================
# Usuario (FN-1, FN-8, FN-14, FN-15)
# =====================================================================

class UsuarioManager(BaseUserManager):
    """Manager mínimo para poder loguear por correo en vez de username."""

    def _crear(self, correo, password, **extra):
        if not correo:
            raise ValueError("El usuario debe tener correo.")
        correo = self.normalize_email(correo)
        usuario = self.model(correo=correo, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, correo, password=None, **extra):
        extra.setdefault("rol", Usuario.Rol.CLIENTE)
        extra.setdefault("estado", Usuario.Estado.ACTIVO)
        return self._crear(correo, password, **extra)

    def create_superuser(self, correo, password=None, **extra):
        extra.setdefault("rol", Usuario.Rol.ADMINISTRADOR)
        extra.setdefault("estado", Usuario.Estado.ACTIVO)
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._crear(correo, password, **extra)


class Usuario(AbstractUser):
    """
    Cliente, técnico y administrador son el mismo modelo con distinto `rol`,
    porque comparten casi todos los campos (FN-1 y FN-8 piden lo mismo salvo
    especialidad/documento, que por eso viven en PerfilTecnico, no aquí).

    Se usa `correo` en vez del `username` de Django para iniciar sesión.
    """

    class Rol(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        TECNICO = "tecnico", "Técnico"
        ADMINISTRADOR = "administrador", "Administrador"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        # Solo técnicos pasan por aquí (FN-8); un cliente nace en ACTIVO (FN-1).
        PENDIENTE_APROBACION = "pendiente_aprobacion", "Pendiente de aprobación"
        RECHAZADO = "rechazado", "Rechazado"
        SUSPENDIDO = "suspendido", "Suspendido"
        # Baja voluntaria desde el perfil (el usuario la pide, el admin la revierte).
        INACTIVO = "inactivo", "Cuenta desactivada"

    username = None  # no se usa: se inicia sesión con correo
    email = None  # se reemplaza por 'correo' para mantener el resto del proyecto en español

    correo = models.EmailField("correo electrónico", unique=True)
    cedula = models.CharField(max_length=10, unique=True, validators=[validar_cedula])
    nombre_completo = models.CharField(
        max_length=150, validators=[validar_nombre])
    telefono = models.CharField(max_length=20, validators=[validar_telefono])
    rol = models.CharField(max_length=20, choices=Rol.choices)
    estado = models.CharField(max_length=25, choices=Estado.choices, default=Estado.ACTIVO)

    # FN-2: dirección y fecha de nacimiento (solo se piden/editan para clientes).
    direccion = models.CharField(max_length=255, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    # FN-4/FN-20: ubicación para calcular distancia y pintar el mapa.
    # Sirve tanto para el cliente (GPS o esta misma dirección) como para el
    # técnico (su punto de referencia dentro de su zona de cobertura).
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)

    # FN-15: motivo y fecha de una suspensión (aplica a cliente o técnico).
    motivo_suspension = models.CharField(max_length=300, blank=True)
    fecha_suspension = models.DateTimeField(null=True, blank=True)

    # FN-14: motivo cuando un admin rechaza a un técnico.
    motivo_rechazo = models.CharField(max_length=300, blank=True)

    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = ["cedula", "nombre_completo", "telefono", "rol"]

    objects = UsuarioManager()

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.nombre_completo} ({self.get_rol_display()})"

    # ---- Reglas de negocio reutilizables (evitan repetir lógica en las vistas) ----

    @property
    def esta_suspendido(self):
        return self.estado == self.Estado.SUSPENDIDO

    @property
    def puede_iniciar_sesion(self):
        """Bloque A: solo un usuario en estado ACTIVO puede iniciar sesión.

        Rechaza suspendidos, rechazados y pendientes de aprobación.
        """
        return self.estado == self.Estado.ACTIVO

    def suspender(self, motivo):
        """FN-15: suspende y, si es técnico, fuerza su disponibilidad a inactivo.

        Bloque A4: además cierra todas sus sesiones activas (borra sus filas
        en django_session) para que la suspensión sea efectiva de inmediato.
        CP-FN15-11: las solicitudes EN_CURSO del técnico suspendido vuelven a
        PENDIENTE (tecnico=None) para que otro técnico pueda tomarlas y no
        queden servicios estancados; se avisa al cliente de cada una.
        """
        self.estado = self.Estado.SUSPENDIDO
        self.motivo_suspension = motivo
        self.fecha_suspension = timezone.now()
        self.save(update_fields=["estado", "motivo_suspension", "fecha_suspension"])
        if self.rol == self.Rol.TECNICO and hasattr(self, "perfil_tecnico"):
            self.perfil_tecnico.disponible = False
            self.perfil_tecnico.save(update_fields=["disponible"])
        if self.rol == self.Rol.TECNICO:
            en_curso = Solicitud.objects.filter(
                tecnico=self, estado=Solicitud.Estado.EN_CURSO)
            for solicitud in en_curso:
                Solicitud.objects.filter(
                    pk=solicitud.pk, estado=Solicitud.Estado.EN_CURSO,
                ).update(
                    estado=Solicitud.Estado.PENDIENTE,
                    tecnico=None, fecha_asignacion=None,
                )
                Notificacion.objects.create(
                    usuario=solicitud.cliente,
                    tipo=Notificacion.Tipo.SOLICITUD_LIBERADA,
                    mensaje=(f"El técnico asignado a tu solicitud #{solicitud.pk} "
                             f"ya no está disponible: la solicitud volvió a "
                             f"pendiente para que otro técnico la tome."),
                    solicitud=solicitud,
                )
        from django.contrib.sessions.models import Session
        for sesion in Session.objects.all():
            datos = sesion.get_decoded()
            if str(datos.get("_auth_user_id")) == str(self.pk):
                sesion.delete()

    def reactivar(self):
        """FN-15: vuelve a 'activo'; el técnico no recupera disponibilidad solo.

        Sirve para cualquier estado no activo (suspendido o cuenta desactivada).
        """
        self.estado = self.Estado.ACTIVO
        self.motivo_suspension = ""
        self.fecha_suspension = None
        self.save(update_fields=["estado", "motivo_suspension", "fecha_suspension"])

    def desactivar(self):
        """Baja voluntaria: el propio usuario desactiva su cuenta.

        Pasa a INACTIVO (no puede iniciar sesión), fuerza disponible=False en
        técnicos y tumba sus sesiones, igual que suspender() pero sin motivo
        disciplinario. El admin la revierte con reactivar().
        """
        self.estado = self.Estado.INACTIVO
        self.motivo_suspension = "Baja voluntaria solicitada por el usuario."
        self.fecha_suspension = timezone.now()
        self.save(update_fields=["estado", "motivo_suspension", "fecha_suspension"])
        if self.rol == self.Rol.TECNICO and hasattr(self, "perfil_tecnico"):
            self.perfil_tecnico.disponible = False
            self.perfil_tecnico.save(update_fields=["disponible"])
        from django.contrib.sessions.models import Session
        for sesion in Session.objects.all():
            datos = sesion.get_decoded()
            if str(datos.get("_auth_user_id")) == str(self.pk):
                sesion.delete()

    def reabrir_revision(self, motivo=""):
        """FN-14: devuelve un técnico aprobado/rechazado a pendiente_aprobacion.

        Vía de corrección si se aprobó sin querer: bloquea la operación
        (disponible=False) pero conserva datos y documentos para re-revisar.
        """
        self.estado = self.Estado.PENDIENTE_APROBACION
        self.motivo_rechazo = motivo
        self.save(update_fields=["estado", "motivo_rechazo"])
        if self.rol == self.Rol.TECNICO and hasattr(self, "perfil_tecnico"):
            self.perfil_tecnico.disponible = False
            self.perfil_tecnico.save(update_fields=["disponible"])


class PerfilTecnico(models.Model):
    """
    Datos exclusivos de un técnico (FN-8, FN-9, FN-10).
    Separado de Usuario porque un cliente nunca tiene estos campos.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_tecnico"
    )
    especialidad = models.CharField(max_length=30, choices=Categoria.choices)
    ciudad = models.CharField(max_length=100)

    # FN-8: obligatorio para completar el registro.
    documento_certificacion = models.FileField(
        upload_to="certificaciones/", validators=[validar_certificacion]
    )
    foto_perfil = models.ImageField(upload_to="fotos_perfil/", null=True, blank=True)

    # FN-9: se editan después del registro; por eso empiezan vacíos/"a convenir".
    precio_referencia = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, blank=True
    )
    zona_cobertura = models.CharField(max_length=255, blank=True)

    # FN-10: solo se puede activar si el técnico ya está aprobado (ver clean()).
    disponible = models.BooleanField(default=False)

    # FN-4/FN-7: se recalculan cada vez que llega una calificación nueva
    # (Calificacion.save más abajo), para no tener que promediar en cada consulta.
    calificacion_promedio = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_calificaciones = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Perfil de técnico"
        verbose_name_plural = "Perfiles de técnico"

    def __str__(self):
        return f"Perfil técnico de {self.usuario.nombre_completo}"

    @property
    def precio_referencia_txt(self):
        """FN-5: 'a convenir' cuando no hay precio definido."""
        if self.precio_referencia is None:
            return "a convenir"
        return f"${self.precio_referencia:,.0f}".replace(",", ".")

    @property
    def disponible_para_solicitudes(self):
        """FN-4/FN-10: un técnico solo aparece si está aprobado, activo y disponible."""
        return (
            self.usuario.estado == Usuario.Estado.ACTIVO
            and self.disponible
        )

    @property
    def especialidades_efectivas(self):
        """Bloque I: principal + extras aprobadas (para el matching FN-4/FN-11)."""
        extras = set(self.documentos.filter(
            estado=DocumentoTecnico.Estado.APROBADO,
        ).values_list("especialidad", flat=True))
        return {self.especialidad} | extras


class IASugerencia(models.Model):
    """Bloque D: el sistema aprende con el uso (capacidad de aprendizaje).

    Cada solicitud creada deja una muestra: qué sugirió la IA y qué categoría
    eligió finalmente el usuario. Sirve para la sustentación ("aprende aunque
    haya pocas reseñas") y para reentrenar (ver core/ia.py + comando
    reentrenar_ia). El texto se guarda normalizado (sin tildes/mayúsculas) más
    su hash como dedup; no es dato sensible.
    NOTA DE LIMPIEZA: en limpiezas de BD esta tabla SE CONSERVA (conocimiento).
    """

    texto_hash = models.CharField(max_length=64, unique=True)
    texto_muestra = models.CharField(max_length=300)
    categoria_sugerida = models.CharField(
        max_length=30, choices=Categoria.choices, null=True, blank=True)
    confianza = models.FloatField(default=0)
    categoria_final = models.CharField(
        max_length=30, choices=Categoria.choices, null=True, blank=True)
    acierto = models.BooleanField(null=True, blank=True)
    origen = models.CharField(max_length=30, default="solicitud_nueva")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"IA:{self.categoria_sugerida}>{self.categoria_final} ({self.texto_muestra[:40]})"


class DocumentoTecnico(models.Model):
    """Certificados extra del técnico (más de uno, actualizables).

    El registro (FN-8) exige un documento principal (`documento_certificacion`);
    aquí el técnico suma los demás conocimientos que quiera acreditar
    (diplomados, cursos, otras áreas) y puede borrar los obsoletos. El admin
    los ve todos en la ficha de revisión (FN-14).
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de aprobación"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    perfil = models.ForeignKey(
        PerfilTecnico, on_delete=models.CASCADE, related_name="documentos")
    nombre = models.CharField(
        max_length=120,
        help_text="Ej. Diplomado en redes eléctricas, Curso de plomería industrial.")
    # Bloque I: a qué habilidad acredita; si el admin la aprueba, se suma a
    # la especialidad principal para el matching (FN-4/FN-11).
    especialidad = models.CharField(
        max_length=30, choices=Categoria.choices, default=Categoria.OTRO)
    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo = models.CharField(max_length=300, blank=True)
    archivo = models.FileField(
        upload_to="certificaciones_extra/", validators=[validar_certificacion])
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_subida"]

    def __str__(self):
        return f"{self.nombre} ({self.perfil.usuario.nombre_completo})"


# =====================================================================
# Solicitud (FN-3, FN-11, FN-12) y sus fotos (FN-3, FN-12)
# =====================================================================

class Solicitud(models.Model):
    """
    FN-3: la crea el cliente. FN-11: un técnico la acepta (modelo abierto:
    se ofrece a todos los técnicos disponibles de la categoría, gana el
    primero que acepta). FN-12: el técnico asignado la finaliza.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_CURSO = "en_curso", "En curso"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    class Urgencia(models.TextChoices):
        NORMAL = "normal", "Normal"
        URGENTE = "urgente", "Urgente"

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_creadas",
        limit_choices_to={"rol": Usuario.Rol.CLIENTE},
    )
    # Null mientras está "pendiente"; FN-11 lo llena al aceptar.
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_asignadas",
        limit_choices_to={"rol": Usuario.Rol.TECNICO}, null=True, blank=True,
    )

    categoria = models.CharField(max_length=30, choices=Categoria.choices)
    descripcion = models.CharField(max_length=300, validators=[MinLengthValidator(10)])
    direccion = models.CharField(max_length=255)
    urgencia = models.CharField(max_length=10, choices=Urgencia.choices, default=Urgencia.NORMAL)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)

    # Bloque H (modo dual marketplace): si se apaga, la solicitud NO sale en
    # el mapa/bandeja de técnicos; el cliente elige él a quién dársela.
    visible_tecnicos = models.BooleanField(default=True)
    # Bloque H: lo que el cliente ofrece pagar; vacío = lo pone el técnico.
    # Editable por el dueño mientras siga pendiente.
    precio_ofrecido = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, blank=True)
    # Bloque H (anti-abuso): el monto del técnico queda PROPUESTO hasta que el
    # cliente lo acepta; solo entonces se habilita el pago.
    monto_aceptado = models.BooleanField(default=False)

    # FN-11: técnicos que ya la rechazaron, para no volver a mostrársela
    # (el criterio no lo exige explícitamente, pero sin esto un técnico
    # que rechazó la seguiría viendo en su bandeja).
    rechazada_por = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="solicitudes_rechazadas", blank=True
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)

    # FN-12: notas opcionales al finalizar.
    notas_finales = models.CharField(max_length=300, blank=True)

    # Bloque C6: monto digitado por el técnico al finalizar (obligatorio en
    # la vista; null mientras la solicitud no está finalizada).
    monto_final = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Solicitud #{self.pk} — {self.get_categoria_display()} ({self.get_estado_display()})"

    # ---- Transiciones de estado, para que las vistas no dupliquen lógica ----

    def aceptar(self, tecnico):
        """FN-11: solo si sigue pendiente.

        UPDATE condicional en una sola sentencia: si dos técnicos aceptan al
        tiempo, solo una fila se actualiza y el otro recibe ValueError.
        Bloque H: si es dirigida a OTRO técnico, nadie más puede tomarla.
        """
        filas = Solicitud.objects.filter(
            pk=self.pk, estado=self.Estado.PENDIENTE,
        ).filter(
            models.Q(tecnico__isnull=True) | models.Q(tecnico=tecnico),
        ).update(
            tecnico=tecnico, estado=self.Estado.EN_CURSO,
            fecha_asignacion=timezone.now(),
        )
        if not filas:
            raise ValueError("La solicitud ya no está disponible.")
        self.refresh_from_db()

    def rechazar(self, tecnico):
        """FN-11: sigue pendiente y disponible para los demás técnicos.

        Bloque H: si era dirigida a quien rechaza, se libera (tecnico=None)
        y vuelve al mapa/bandeja general; igual no la vuelve a ver él.
        """
        if self.tecnico_id == tecnico.pk:
            self.tecnico = None
            self.save(update_fields=["tecnico"])
        self.rechazada_por.add(tecnico)

    def finalizar(self, notas="", monto_final=None):
        """FN-12: monto manual obligatorio + solo si está en curso.

        UPDATE condicional atómico, igual que aceptar().
        """
        if monto_final is None or monto_final <= 0:
            raise ValueError("El monto final es obligatorio y debe ser mayor que cero.")
        filas = Solicitud.objects.filter(
            pk=self.pk, estado=self.Estado.EN_CURSO
        ).update(
            estado=self.Estado.FINALIZADA, fecha_finalizacion=timezone.now(),
            notas_finales=notas or "", monto_final=monto_final,
            monto_aceptado=False,
        )
        if not filas:
            raise ValueError("Solo se puede finalizar una solicitud en curso.")
        self.refresh_from_db()

    def confirmar_monto(self):
        """Bloque H: el cliente acepta el monto propuesto y habilita el pago."""
        if self.estado != self.Estado.FINALIZADA or not self.monto_final:
            raise ValueError("No hay monto por confirmar.")
        self.monto_aceptado = True
        self.save(update_fields=["monto_aceptado"])

    def rechazar_monto(self):
        """Bloque H: el cliente rechaza el monto; vuelve a en curso para ajuste."""
        if self.estado != self.Estado.FINALIZADA:
            raise ValueError("Solo se puede rechazar el monto de una finalizada.")
        self.estado = self.Estado.EN_CURSO
        self.monto_final = None
        self.monto_aceptado = False
        self.save(update_fields=["estado", "monto_final", "monto_aceptado"])

    def cancelar(self):
        """Bloque C7: solo el cliente dueño y solo si sigue pendiente."""
        if self.estado != self.Estado.PENDIENTE:
            raise ValueError("Solo se puede cancelar una solicitud pendiente.")
        self.estado = self.Estado.CANCELADA
        self.save(update_fields=["estado"])

    @property
    def puede_calificarse(self):
        """FN-7."""
        return self.estado == self.Estado.FINALIZADA and not hasattr(self, "calificacion")

    @property
    def puede_pagarse(self):
        """FN-17 + Bloque H: exige monto aceptado por el cliente (anti-abuso)."""
        return (
            self.estado == self.Estado.FINALIZADA
            and self.monto_aceptado
            and not (
                hasattr(self, "pago") and self.pago.estado == Pago.Estado.EXITOSO
            )
        )


class FotoSolicitud(models.Model):
    """FN-3: hasta 3 fotos de evidencia al crear. FN-12: foto opcional al finalizar."""

    class Tipo(models.TextChoices):
        EVIDENCIA = "evidencia", "Evidencia del daño"
        FINALIZACION = "finalizacion", "Evidencia de finalización"

    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name="fotos")
    imagen = models.ImageField(upload_to="solicitudes/", validators=[validar_foto])
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.EVIDENCIA)

    def __str__(self):
        return f"Foto {self.get_tipo_display()} de la solicitud #{self.solicitud_id}"


# =====================================================================
# Calificación (FN-7, FN-13)
# =====================================================================

class Calificacion(models.Model):
    """FN-7: una por solicitud finalizada, no editable después de enviada."""

    solicitud = models.OneToOneField(Solicitud, on_delete=models.CASCADE, related_name="calificacion")
    estrellas = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.CharField(max_length=300, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    # Bloque F2: la IA de sentimiento marca True cuando el comentario trae
    # lenguaje agresivo o es incongruente (5? con texto muy negativo); el
    # admin lo revisa (ver CalificacionAdmin + historial del técnico).
    revision_admin = models.BooleanField(default=False)

    # Moderación admin: oculta no se muestra en el perfil público ni cuenta
    # para el promedio (ver set_oculta + _recalcular_promedio_tecnico).
    oculta = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.estrellas}★ a {self.solicitud.tecnico} (solicitud #{self.solicitud_id})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._recalcular_promedio_tecnico()

    def _recalcular_promedio_tecnico(self):
        """FN-7: cada calificación nueva recalcula el promedio usado en FN-4.

        Solo cuentan las visibles (oculta=False): al moderar una reseña el
        promedio del técnico se corrige solo.
        """
        perfil = self.solicitud.tecnico.perfil_tecnico
        calificaciones = Calificacion.objects.filter(
            solicitud__tecnico=self.solicitud.tecnico, oculta=False)
        total = calificaciones.count()
        promedio = calificaciones.aggregate(models.Avg("estrellas"))["estrellas__avg"] or 0
        perfil.total_calificaciones = total
        perfil.calificacion_promedio = round(promedio, 2)
        perfil.save(update_fields=["total_calificaciones", "calificacion_promedio"])

    def set_oculta(self, oculta):
        """Moderación: oculta/muestra la reseña y recalcula el promedio."""
        self.oculta = oculta
        self.save(update_fields=["oculta"])
        self._recalcular_promedio_tecnico()


# =====================================================================
# Notificaciones (FN-19)
# =====================================================================

class Notificacion(models.Model):
    """FN-19: una notificación in-app dirigida a un solo usuario."""

    class Tipo(models.TextChoices):
        SOLICITUD_CREADA = "solicitud_creada", "Solicitud creada"
        SOLICITUD_ACEPTADA = "solicitud_aceptada", "Solicitud aceptada"
        SOLICITUD_RECHAZADA = "solicitud_rechazada", "Solicitud rechazada"
        SOLICITUD_FINALIZADA = "solicitud_finalizada", "Solicitud finalizada"
        SOLICITUD_CANCELADA = "solicitud_cancelada", "Solicitud cancelada"
        # CP-FN15-11: el técnico asignado fue suspendido y la solicitud volvió
        # a pendiente para que otro técnico la tome.
        SOLICITUD_LIBERADA = "solicitud_liberada", "Solicitud devuelta a pendiente"
        TECNICO_APROBADO = "tecnico_aprobado", "Técnico aprobado"
        TECNICO_RECHAZADO = "tecnico_rechazado", "Técnico rechazado"
        INFO_SOLICITADA = "info_solicitada", "Información solicitada"
        USUARIO_SUSPENDIDO = "usuario_suspendido", "Usuario suspendido"
        CALIFICACION_RECIBIDA = "calificacion_recibida", "Calificación recibida"
        PAGO_EXITOSO = "pago_exitoso", "Pago exitoso"
        PAGO_FALLIDO = "pago_fallido", "Pago fallido"
        # Bloque F2: aviso al admin cuando una calificación queda en revisión.
        CALIFICACION_ALERTA = "calificacion_alerta", "Calificación en revisión"
        # Bloque G: revisión reabierta, baja voluntaria y reseña moderada.
        TECNICO_REABIERTO = "tecnico_reabierto", "Revisión de técnico reabierta"
        CUENTA_DESACTIVADA = "cuenta_desactivada", "Cuenta desactivada"
        RESENA_MODERADA = "resena_moderada", "Reseña moderada"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones"
    )
    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    mensaje = models.CharField(max_length=255)
    # FN-19: si viene de una solicitud, tocarla navega a su detalle.
    solicitud = models.ForeignKey(
        Solicitud, on_delete=models.CASCADE, related_name="notificaciones", null=True, blank=True
    )
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"[{'leída' if self.leida else 'nueva'}] {self.mensaje}"


# =====================================================================
# Pagos y comisión (FN-17, FN-18)
# =====================================================================

class ConfiguracionComision(models.Model):
    """
    FN-18: porcentaje configurable, no fijo en el código.
    Se maneja como fila única (singleton simple, sin librerías extra).
    """

    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de comisión"
        verbose_name_plural = "Configuración de comisión"

    def __str__(self):
        return f"Comisión actual: {self.porcentaje}%"

    @classmethod
    def actual(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class Pago(models.Model):
    """FN-17: pago en modo sandbox de la pasarela, ver nota en el documento de sprints."""

    class Medio(models.TextChoices):
        TARJETA = "tarjeta", "Tarjeta"
        PSE = "pse", "PSE"
        BILLETERA = "billetera", "Billetera digital"
        EFECTIVO = "efectivo", "Efectivo"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EXITOSO = "exitoso", "Exitoso"
        FALLIDO = "fallido", "Fallido"

    solicitud = models.OneToOneField(Solicitud, on_delete=models.PROTECT, related_name="pago")
    medio_pago = models.CharField(max_length=15, choices=Medio.choices)
    monto = models.DecimalField(max_digits=10, decimal_places=0)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    # Id que devuelve la pasarela en sandbox (Wompi/ePayco/Mercado Pago); nunca
    # se guardan datos sensibles como número de tarjeta o CVV (regla de FN-17).
    referencia_pasarela = models.CharField(max_length=100, blank=True)
    motivo_fallo = models.CharField(max_length=255, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pago {self.get_estado_display()} — solicitud #{self.solicitud_id}"

    def marcar_exitoso(self, referencia_pasarela):
        """FN-17 + FN-18: al quedar exitoso, dispara el cálculo de comisión."""
        self.estado = self.Estado.EXITOSO
        self.referencia_pasarela = referencia_pasarela
        self.save(update_fields=["estado", "referencia_pasarela"])
        Comision.calcular_para(self)

    def marcar_fallido(self, motivo):
        self.estado = self.Estado.FALLIDO
        self.motivo_fallo = motivo
        self.save(update_fields=["estado", "motivo_fallo"])


class Comision(models.Model):
    """FN-18: se calcula automáticamente cuando un Pago pasa a exitoso."""

    pago = models.OneToOneField(Pago, on_delete=models.CASCADE, related_name="comision")
    porcentaje_aplicado = models.DecimalField(max_digits=5, decimal_places=2)
    monto_comision = models.DecimalField(max_digits=10, decimal_places=0)
    monto_neto_tecnico = models.DecimalField(max_digits=10, decimal_places=0)
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comisión de ${self.monto_comision:,.0f} (pago #{self.pago_id})".replace(",", ".")

    @classmethod
    def calcular_para(cls, pago):
        """
        FN-18: monto de comisión = monto × porcentaje; neto = monto − comisión.
        Guarda el porcentaje aplicado (no solo el actual) para que un cambio
        futuro de configuración no altere comisiones ya calculadas.
        """
        porcentaje = ConfiguracionComision.actual().porcentaje
        monto_comision = round(pago.monto * porcentaje / 100)
        return cls.objects.create(
            pago=pago,
            porcentaje_aplicado=porcentaje,
            monto_comision=monto_comision,
            monto_neto_tecnico=pago.monto - monto_comision,
        )
