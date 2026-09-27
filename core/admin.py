from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Calificacion, Comision, ConfiguracionComision, DocumentoTecnico,
    FotoSolicitud, IASugerencia, Notificacion, Pago, PerfilTecnico,
    Solicitud, Usuario,
)

# Motivo auditable cuando se suspende desde /admin/ sin detallar el caso.
MOTIVO_SUSPENSION_ADMIN = (
    "Suspendido por el administrador desde /admin/ (motivo detallado pendiente de registro)."
)


@admin.action(description="Aprobar técnicos pendientes seleccionados (FN-14)")
def aprobar_tecnicos(modeladmin, request, queryset):
    """B5: equivale al botón Aprobar de /panel/tecnicos/."""
    pendientes = queryset.filter(
        rol=Usuario.Rol.TECNICO, estado=Usuario.Estado.PENDIENTE_APROBACION
    ).select_related("perfil_tecnico")
    total = 0
    for tecnico in pendientes:
        tecnico.estado = Usuario.Estado.ACTIVO
        tecnico.motivo_rechazo = ""
        tecnico.save(update_fields=["estado", "motivo_rechazo"])
        tecnico.perfil_tecnico.disponible = False
        tecnico.perfil_tecnico.save(update_fields=["disponible"])
        Notificacion.objects.create(
            usuario=tecnico,
            tipo=Notificacion.Tipo.TECNICO_APROBADO,
            mensaje="Tu registro fue aprobado. Ya puedes activar tu disponibilidad.",
        )
        total += 1
    if total:
        modeladmin.message_user(request, f"{total} técnico(s) aprobado(s).")
    else:
        modeladmin.message_user(
            request, "Ningún seleccionado era técnico pendiente de aprobación.",
            level="warning",
        )


@admin.action(description="Suspender usuarios seleccionados (FN-15)")
def suspender_usuarios(modeladmin, request, queryset):
    """B5: equivale a Suspender en /panel/usuarios/.

    Usa Usuario.suspender() (fuerza disponible=False y tumba sesiones) y deja
    un motivo auditable en motivo_suspension + fecha_suspension.
    """
    total = 0
    for usuario in queryset.exclude(pk=request.user.pk):
        usuario.suspender(MOTIVO_SUSPENSION_ADMIN)
        Notificacion.objects.create(
            usuario=usuario,
            tipo=Notificacion.Tipo.USUARIO_SUSPENDIDO,
            mensaje=f"Tu cuenta fue suspendida. Motivo: {MOTIVO_SUSPENSION_ADMIN}",
        )
        total += 1
    modeladmin.message_user(request, f"{total} usuario(s) suspendido(s).")


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    # UserAdmin trae fieldsets pensados para 'username'; como aquí no existe,
    # se sobreescriben para que el admin no reviente al abrir un usuario.
    ordering = ["-date_joined"]
    list_display = ["correo", "nombre_completo", "rol", "estado", "is_staff"]
    list_filter = ["rol", "estado"]
    search_fields = ["correo", "cedula", "nombre_completo"]
    actions = [aprobar_tecnicos, suspender_usuarios]
    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Datos personales", {"fields": ("nombre_completo", "cedula", "telefono",
                                          "direccion", "fecha_nacimiento", "latitud", "longitud")}),
        ("Estado", {"fields": ("rol", "estado", "motivo_rechazo",
                                "motivo_suspension", "fecha_suspension")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": (
            "correo", "password1", "password2", "cedula", "nombre_completo", "telefono", "rol",
        )}),
    )


@admin.register(PerfilTecnico)
class PerfilTecnicoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "especialidad", "ciudad", "disponible", "calificacion_promedio"]
    list_filter = ["especialidad", "disponible"]


class FotoSolicitudInline(admin.TabularInline):
    model = FotoSolicitud
    extra = 0


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ["id", "categoria", "estado", "cliente", "tecnico", "urgencia", "fecha_creacion"]
    list_filter = ["estado", "categoria", "urgencia"]
    inlines = [FotoSolicitudInline]


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    """Bloque F2: las calificaciones con lenguaje agresivo/incongruente
    quedan con revision_admin=True; el filtro las agrupa para el admin.

    Bloque G: oculta saca la reseña del perfil público y del promedio
    (ver Calificacion.set_oculta)."""

    list_display = ["solicitud", "estrellas", "revision_admin", "oculta", "fecha_creacion"]
    list_filter = ["revision_admin", "oculta", "estrellas"]


@admin.register(DocumentoTecnico)
class DocumentoTecnicoAdmin(admin.ModelAdmin):
    """Bloque G: certificados extra del técnico (el principal va en el perfil)."""

    list_display = ["nombre", "perfil", "fecha_subida"]
    search_fields = ["nombre", "perfil__usuario__nombre_completo"]


admin.site.register(Notificacion)
admin.site.register(Pago)
admin.site.register(Comision)


@admin.register(IASugerencia)
class IASugerenciaAdmin(admin.ModelAdmin):
    """Bloque D: muestras del aprendizaje (se conservan en limpiezas)."""

    list_display = ["texto_muestra", "categoria_sugerida", "categoria_final",
                    "acierto", "fecha_creacion"]
    list_filter = ["acierto", "categoria_final", "origen"]
    search_fields = ["texto_muestra"]


@admin.register(ConfiguracionComision)
class ConfiguracionComisionAdmin(admin.ModelAdmin):
    """E3 / FN-18: el % de comisión es editable por el admin desde /admin/.

    Es una fila única (singleton pk=1, creada vía ConfiguracionComision.actual());
    se bloquea el borrado y el alta manual para no romper esa invariante.
    """

    list_display = ["porcentaje", "actualizado_en"]
    readonly_fields = ["actualizado_en"]

    def has_add_permission(self, request):
        return not ConfiguracionComision.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
