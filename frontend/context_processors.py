"""D4 / FN-19: contexto global de la campana de notificaciones.

Aporta `n_notif` (no-leídas del usuario en sesión) a TODAS las plantillas,
reemplazando el `n_notif=3` hardcodeado que antes ponía `_ctx` en cada vista.
"""

from core.models import Notificacion


def campana(request):
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        return {
            "n_notif": Notificacion.objects.filter(
                usuario=usuario, leida=False
            ).count()
        }
    return {"n_notif": 0}
