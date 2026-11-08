"""D4 / FN-19: contexto global de la campana de notificaciones.

Aporta `n_notif` (no-leídas del usuario en sesión) a TODAS las plantillas,
reemplazando el `n_notif=3` hardcodeado que antes ponía `_ctx` en cada vista.
"""

from core.models import Direccion, Notificacion, Usuario


def campana(request):
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        datos = {
            "n_notif": Notificacion.objects.filter(
                usuario=usuario, leida=False
            ).count()
        }
        if getattr(usuario, "rol", None) == Usuario.Rol.CLIENTE:
            direcciones = list(
                Direccion.objects.filter(cliente=usuario).order_by(
                    "-es_principal", "etiqueta", "-fecha_creacion")
            )
            principal = next(
                (d for d in direcciones if d.es_principal), None)
            datos["direcciones"] = direcciones
            datos["direccion_principal"] = principal
            datos["direccion_activa"] = principal or (
                direcciones[0] if direcciones else None)
        return datos
    return {"n_notif": 0, "direcciones": [], "direccion_principal": None,
            "direccion_activa": None}
