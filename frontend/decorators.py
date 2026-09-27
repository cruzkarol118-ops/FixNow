"""Bloque A3: guards de autenticación y rol para las vistas privadas."""

from functools import wraps

from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse


def _redigir_login(request):
    login_url = reverse("login")
    return redirect(f"{login_url}?next={request.path}")


def rol_requerido(*roles_permitidos):
    """Exige sesión, estado ACTIVO y uno de los roles dados.

    - Sin sesión → 302 al login (?next=...).
    - Sesión con estado no activo (suspendido/rechazado/pendiente) → cierra
      la sesión y 302 al login (la suspensión es efectiva server-side).
    - Rol distinto → 403 (PermissionDenied).
    """

    def decorador(vista):
        @wraps(vista)
        def _envuelta(request, *args, **kwargs):
            usuario = request.user
            if not usuario.is_authenticated:
                return _redigir_login(request)
            if not getattr(usuario, "puede_iniciar_sesion", False):
                logout(request)
                return redirect("login")
            if usuario.rol not in roles_permitidos:
                raise PermissionDenied("No tienes permiso para ver esta página.")
            return vista(request, *args, **kwargs)

        return _envuelta

    return decorador


def admin_requerido(vista):
    """Guarda de `panel/*`: solo staff o superuser con estado ACTIVO.

    - Sin sesión → 302 al login.
    - Suspendido/rechazado/pendiente → logout + 302 al login.
    - Autenticado sin ser staff/superuser (p. ej. un cliente) → 403.
    """

    @wraps(vista)
    def _envuelta(request, *args, **kwargs):
        usuario = request.user
        if not usuario.is_authenticated:
            return _redigir_login(request)
        if not getattr(usuario, "puede_iniciar_sesion", False):
            logout(request)
            return redirect("login")
        if not (usuario.is_staff or usuario.is_superuser):
            raise PermissionDenied("Esta sección es solo para el personal autorizado.")
        return vista(request, *args, **kwargs)

    return _envuelta
