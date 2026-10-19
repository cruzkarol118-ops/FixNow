import math

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import (
    CalificarForm, CambioPasswordForm, DecisionTecnicoForm, DesactivarCuentaForm,
    DocumentoDecisionForm, DocumentoTecnicoForm, FinalizarSolicitudForm,
    MontoDecisionForm, PagoSimuladoForm, PerfilClienteForm, PerfilTecnicoForm,
    PrecioEditarForm, RegistroClienteForm, RegistroTecnicoForm,
    ResenaModerarForm, SolicitudNuevaForm, SuspenderUsuarioForm,
)
from core.ia import analizar_sentimiento, huella, predecir_categoria
from core.models import (
    Calificacion, Categoria, Comision, ConfiguracionComision, DocumentoTecnico,
    FotoSolicitud, IASugerencia, Notificacion, Pago, PerfilTecnico,
    Solicitud, Usuario,
)
from core.validators import validar_foto

from .decorators import admin_requerido, rol_requerido


# Bloque F: catálogo e iconos viven aquí (antes en datos_falsos.py, que queda
# solo como referencia histórica y sin ningún uso en vistas).
ICONOS_CATEGORIA = {
    "plomeria": "bi-droplet-half",
    "electricidad": "bi-lightning-charge-fill",
    "cerrajeria": "bi-key-fill",
    "electrodomesticos": "bi-tv-fill",
    "otro": "bi-tools",
}
CATEGORIAS = [
    {"id": valor, "nombre": etiqueta, "icono": ICONOS_CATEGORIA.get(valor, "bi-tools")}
    for valor, etiqueta in Categoria.choices
]


def haversine_km(lat1, lng1, lat2, lng2):
    """Distancia en km entre dos coordenadas (FN-4)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _ctx(rol, **extra):
    """Contexto base de cada vista.

    D4: ya NO pone `n_notif` hardcodeado; el conteo real de no-leídas lo
    aporta `frontend.context_processors.campana` en todas las plantillas.
    Bloque F: tampoco trae cliente mock; cada vista real pasa
    `request.user` vía `extra`.
    """
    base = {"rol": rol}
    base.update(extra)
    return base


def _destino_por_rol(usuario):
    """Bloque A1: redirección post-login según rol."""
    if usuario.is_staff or usuario.is_superuser or usuario.rol == Usuario.Rol.ADMINISTRADOR:
        return redirect("admin_tecnicos")
    if usuario.rol == Usuario.Rol.TECNICO:
        return redirect("tecnico_solicitudes")
    return redirect("cliente_inicio")


# ---------- Público ----------
def landing(request):
    return render(request, "publico/landing.html", _ctx("publico", categorias=CATEGORIAS))


def login_view(request):
    """Bloque A1+A4: authenticate()+login() con correo+password.

    Rechaza credenciales malas (200 con error, sin redirect) y usuarios cuyo
    estado no sea ACTIVO (suspendido/rechazado/pendiente_aprobacion).
    """
    if request.user.is_authenticated:
        return _destino_por_rol(request.user)
    error = ""
    correo = ""
    if request.method == "POST":
        correo = (request.POST.get("correo") or "").strip().lower()
        clave = request.POST.get("clave") or ""
        usuario = authenticate(request, username=correo, password=clave)
        if usuario is None:
            error = "Correo o contraseña incorrectos."
        elif not usuario.puede_iniciar_sesion:
            mensajes_estado = {
                Usuario.Estado.SUSPENDIDO: "Tu cuenta está suspendida. Contáctanos para más información.",
                Usuario.Estado.RECHAZADO: "Tu registro fue rechazado. Contáctanos para más información.",
                Usuario.Estado.PENDIENTE_APROBACION: "Tu cuenta está pendiente de aprobación.",
                Usuario.Estado.INACTIVO: "Desactivaste tu cuenta. Contáctanos si quieres reactivarla.",
            }
            error = mensajes_estado.get(
                usuario.estado, "No puedes iniciar sesión con esta cuenta.")
            # El pendiente no puede entrar a ver su notificación: la observación
            # del admin (pedir info) se le muestra aquí mismo en el login.
            if usuario.estado == Usuario.Estado.PENDIENTE_APROBACION and (
                    usuario.motivo_rechazo or "").strip():
                error += f" Observación del administrador: {usuario.motivo_rechazo.strip()}"
        else:
            login(request, usuario)
            # Los mensajes pendientes (ej. "Sesión cerrada correctamente" del
            # logout anterior) sobrevivirían al login y aparecerían en la
            # sesión nueva: se consumen aquí para que un login fresco no
            # muestre avisos de la sesión anterior.
            list(messages.get_messages(request))
            return _destino_por_rol(usuario)
    return render(request, "publico/login.html", _ctx("publico", error=error, correo=correo))


def logout_view(request):
    """Bloque A2: cierra la sesión y vuelve al landing."""
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect("landing")


def registro_cliente(request):
    if request.method == "POST":
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)  # FN-1: autentica automáticamente tras registrarse
            return redirect("cliente_inicio")
    else:
        form = RegistroClienteForm()
    return render(request, "publico/registro_cliente.html", _ctx("publico", form=form))


def registro_tecnico(request):
    if request.method == "POST":
        form = RegistroTecnicoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            # FN-8: a diferencia del cliente, NO se loguea automáticamente:
            # queda pendiente de aprobación (FN-14).
            return render(request, "publico/registro_tecnico_ok.html", _ctx("publico"))
    else:
        form = RegistroTecnicoForm()
    return render(request, "publico/registro_tecnico.html", _ctx("publico", form=form))


@login_required(login_url="login")
def cambiar_password(request):
    """Bloque A5: cambio de contraseña exigiendo la actual + política."""
    if request.method == "POST":
        form = CambioPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            usuario = form.save()
            update_session_auth_hash(request, usuario)
            messages.success(request, "Contraseña actualizada correctamente.")
            return _destino_por_rol(request.user)
    else:
        form = CambioPasswordForm(user=request.user)
    rol_ctx = (
        "admin"
        if (request.user.is_staff or request.user.is_superuser)
        else request.user.rol
    )
    return render(request, "publico/cambiar_password.html", _ctx(rol_ctx, form=form))


# ---------- Cliente ----------
@rol_requerido(Usuario.Rol.CLIENTE)
def cliente_inicio(request):
    """Bloque F: inicio con datos reales (antes mocks de datos_falsos).

    - Últimos técnicos disponibles (rol técnico + estado activo +
      disponible=True, más recientes primero, máx 4) con su tarjeta real.
    - Solicitud activa del usuario (pendiente o en_curso, la más reciente),
      o nada si no tiene ninguna.
    """
    cliente = request.user
    disponibles = (
        PerfilTecnico.objects.select_related("usuario").filter(
            disponible=True,
            usuario__rol=Usuario.Rol.TECNICO,
            usuario__estado=Usuario.Estado.ACTIVO,
        ).order_by("-usuario__date_joined")[:4]
    )
    tarjetas = []
    for perfil in disponibles:
        km = None
        if (cliente.latitud is not None and cliente.longitud is not None
                and perfil.usuario.latitud is not None
                and perfil.usuario.longitud is not None):
            km = round(haversine_km(
                cliente.latitud, cliente.longitud,
                perfil.usuario.latitud, perfil.usuario.longitud), 1)
        tarjetas.append(_tarjeta_tecnico(perfil, km))

    # Todas las activas (pendientes + en curso), no solo la última: con varias
    # solicitudes el inicio mostraba una sola y el resto quedaba escondido.
    activas = []
    for activa in (
        Solicitud.objects.filter(
            cliente=cliente,
            estado__in=[Solicitud.Estado.PENDIENTE, Solicitud.Estado.EN_CURSO],
        ).select_related("tecnico").order_by("-fecha_creacion")[:4]
    ):
        activas.append({
            "pk": activa.pk,
            "icono": _ICONO_CATEGORIA.get(activa.categoria, "bi-tools"),
            "categoria": activa.get_categoria_display(),
            "tecnico": activa.tecnico.nombre_completo if activa.tecnico_id else "Sin asignar",
            "descripcion": activa.descripcion,
            "estado": activa.estado,
        })
    return render(request, "cliente/inicio.html", _ctx(
        "cliente", cliente=cliente, categorias=CATEGORIAS,
        activas=activas, tecnicos=tarjetas))


@rol_requerido(Usuario.Rol.CLIENTE)
def solicitud_nueva(request):
    """C1 / FN-3: crea la Solicitud real con evidencias y notificación.

    Exige la dirección del perfil (redirige a editarlo si falta). Al crear,
    va a técnicos disponibles (FN-4).
    """
    cliente = request.user
    if not (cliente.direccion or "").strip():
        messages.warning(
            request, "Primero agrega tu dirección en el perfil para poder crear solicitudes.")
        return redirect("cliente_perfil")

    # Bloque H: venir de Elegir (?tecnico=<id>) = crearla dirigida a él.
    dirigido_a = None
    dirigido_id = request.GET.get("tecnico") or request.POST.get("tecnico_id") or ""
    if dirigido_id:
        try:
            dirigido_a = PerfilTecnico.objects.select_related("usuario").get(
                usuario__pk=int(dirigido_id),
                disponible=True,
                usuario__rol=Usuario.Rol.TECNICO,
                usuario__estado=Usuario.Estado.ACTIVO,
            )
        except (PerfilTecnico.DoesNotExist, TypeError, ValueError):
            messages.error(request, "Ese técnico ya no está disponible.")
            return redirect("tecnicos")
    # La casilla visible_tecnicos va marcada por defecto; en reintento con
    # error se respeta lo que el usuario había marcado.
    visible_checked = (
        request.POST.get("visible_tecnicos") if request.method == "POST" else True)
    contexto_base = {
        "categorias": CATEGORIAS,
        "preseleccion": request.GET.get("categoria", ""),
        "direccion_perfil": cliente.direccion,
        "aviso_ia": "",
        "dirigido_a": dirigido_a,
        "visible_checked": visible_checked,
    }
    # F1: ?sugerir=1&texto=... → la IA sugiere y preselecciona la categoría.
    # No bloquea nada: si no hay texto o no hay sklearn, se ignora en silencio.
    if request.method == "GET" and request.GET.get("sugerir") == "1":
        texto_libre = (request.GET.get("texto") or "").strip()
        sugerida, _conf = predecir_categoria(texto_libre)
        if sugerida:
            contexto_base["preseleccion"] = sugerida
            contexto_base["aviso_ia"] = (
                f"IA sugiere: {_NOMBRE_CATEGORIA.get(sugerida, sugerida)}")
        return render(request, "cliente/solicitud_nueva.html", _ctx(
            "cliente", cliente=cliente, form=None, errores_fotos=[],
            datos={"descripcion": texto_libre}, **contexto_base))
    if request.method == "POST":
        form = SolicitudNuevaForm(request.POST)
        fotos = request.FILES.getlist("fotos")
        errores_fotos = _validar_fotos_evidencia(fotos)
        if form.is_valid() and not errores_fotos:
            datos = form.cleaned_data
            # Bloque H: si viene dirigida, el técnico debe cubrir la categoría.
            if dirigido_a is not None and (
                    datos["categoria"] not in dirigido_a.especialidades_efectivas):
                messages.error(
                    request,
                    f"{dirigido_a.usuario.nombre_completo} no atiende esa categoría.")
                return render(request, "cliente/solicitud_nueva.html", _ctx(
                    "cliente", cliente=cliente, form=form, errores_fotos=errores_fotos,
                    datos=request.POST, **contexto_base))
            with transaction.atomic():
                solicitud = Solicitud.objects.create(
                    cliente=cliente,
                    categoria=datos["categoria"],
                    descripcion=datos["descripcion"],
                    direccion=datos["direccion"],
                    urgencia=datos["urgencia"],
                    precio_ofrecido=datos.get("precio_ofrecido"),
                    visible_tecnicos=bool(datos.get("visible_tecnicos", True)),
                    tecnico=dirigido_a.usuario if dirigido_a else None,
                )
                for foto in fotos:
                    FotoSolicitud.objects.create(
                        solicitud=solicitud, imagen=foto,
                        tipo=FotoSolicitud.Tipo.EVIDENCIA,
                    )
                Notificacion.objects.create(
                    usuario=cliente,
                    tipo=Notificacion.Tipo.SOLICITUD_CREADA,
                    mensaje=f"Tu solicitud #{solicitud.pk} de "
                            f"{solicitud.get_categoria_display()} fue creada.",
                    solicitud=solicitud,
                )
            # Bloque D: la muestra (sugerencia vs elección real) enseña al
            # sistema con el uso; no bloquea nada si falla.
            try:
                sug_d, conf_d = predecir_categoria(datos["descripcion"])
                h, norm = huella(datos["descripcion"])
                IASugerencia.objects.get_or_create(
                    texto_hash=h,
                    defaults={
                        "texto_muestra": norm[:300],
                        "categoria_sugerida": sug_d,
                        "confianza": conf_d,
                        "categoria_final": datos["categoria"],
                        "acierto": (sug_d == datos["categoria"]
                                    if sug_d else None),
                        "origen": "solicitud_nueva",
                    },
                )
            except Exception:
                pass
            request.session["solicitud_actual_id"] = solicitud.pk
            request.session.pop("preseleccion", None)
            if dirigido_a is not None:
                messages.success(
                    request, f"Solicitud #{solicitud.pk} creada y dirigida a "
                             f"{dirigido_a.usuario.nombre_completo}: él decide si la acepta.")
            else:
                messages.success(request, "Solicitud creada. Elige un técnico disponible.")
            return redirect("tecnicos")
        # F1: si el POST no trae categoría pero sí descripción, la IA sugiere
        # una y la preselecciona (el usuario confirma reenviando). Si no hay
        # sklearn, predecir_categoria devuelve None y se muestra el error
        # normal del formulario.
        if "categoria" in form.errors:
            descripcion_txt = (request.POST.get("descripcion") or "").strip()
            sugerida, _conf = predecir_categoria(descripcion_txt)
            if sugerida:
                contexto_base["preseleccion"] = sugerida
                contexto_base["aviso_ia"] = (
                    f"IA sugiere: {_NOMBRE_CATEGORIA.get(sugerida, sugerida)}")
        return render(request, "cliente/solicitud_nueva.html", _ctx(
            "cliente", cliente=cliente, form=form, errores_fotos=errores_fotos,
            datos=request.POST, **contexto_base))
    return render(request, "cliente/solicitud_nueva.html", _ctx(
        "cliente", cliente=cliente, form=None, errores_fotos=[], datos={},
        **contexto_base))


def _validar_fotos_evidencia(fotos):
    """C1: máx 3 fotos jpg/png de 5MB (reutiliza validar_foto del modelo)."""
    errores = []
    if len(fotos) > 3:
        errores.append("Puedes subir máximo 3 fotos.")
        fotos = fotos[:3]
    for foto in fotos:
        try:
            validar_foto(foto)
        except ValidationError as exc:
            errores.append(f"{foto.name}: {'; '.join(exc.messages)}")
    return errores


_ICONO_CATEGORIA = {c["id"]: c["icono"] for c in CATEGORIAS}
_NOMBRE_CATEGORIA = {c["id"]: c["nombre"] for c in CATEGORIAS}


def _iniciales(nombre):
    partes = (nombre or "").split()
    if len(partes) > 1:
        return (partes[0][0] + partes[1][0]).upper()
    return ((nombre or "?")[:2]).upper()


def _tarjeta_tecnico(perfil, km):
    """C2: dicta la tarjeta con la forma que espera tarjeta_tecnico.html."""
    usuario = perfil.usuario
    if perfil.total_calificaciones and perfil.calificacion_promedio:
        rating = float(perfil.calificacion_promedio)
        rating_txt = f"{rating:.1f}".replace(".", ",")
    else:
        rating = None
        rating_txt = "Sin calificaciones"
    return {
        "id": usuario.pk,
        "nombre": usuario.nombre_completo,
        "iniciales": _iniciales(usuario.nombre_completo),
        "categoria": perfil.especialidad,
        "especialidad": _NOMBRE_CATEGORIA.get(perfil.especialidad, perfil.especialidad),
        "icono": _ICONO_CATEGORIA.get(perfil.especialidad, "bi-tools"),
        "rating": rating,
        "rating_txt": rating_txt,
        "resenas": perfil.total_calificaciones,
        "precio": perfil.precio_referencia,
        "precio_txt": perfil.precio_referencia_txt,
        "lat": usuario.latitud,
        "lng": usuario.longitud,
        "km": km,
    }


@rol_requerido(Usuario.Rol.CLIENTE)
def tecnicos(request):
    """C2 / FN-4 + C3 / FN-20: listado y mapa reales de técnicos.

    Filtra por la especialidad == categoría de la solicitud pendiente ELEGIDA
    (?solicitud=<id>; por defecto la más reciente). Sin pendientes, muestra
    todos los disponibles. Solo disponible=True y usuarios activos. Ordena por
    cercanía (Haversine) o por calificación (?orden=calificacion).
    ?elegir=<id> dirige ESA solicitud al técnico (él acepta/rechaza).
    """
    cliente = request.user
    pendientes = list(Solicitud.objects.filter(
        cliente=cliente, estado=Solicitud.Estado.PENDIENTE
    ).order_by("-fecha_creacion"))
    sol_actual = pendientes[0] if pendientes else None
    if "solicitud" in request.GET and pendientes:
        try:
            pedida = int(request.GET.get("solicitud"))
            elegida = next((s for s in pendientes if s.pk == pedida), None)
            if elegida is None:
                messages.error(request, "Esa solicitud ya no está pendiente.")
                return redirect("tecnicos")
            sol_actual = elegida
        except (TypeError, ValueError):
            messages.error(request, "Solicitud no válida.")
            return redirect("tecnicos")
    categoria = sol_actual.categoria if sol_actual else None

    disponibles = PerfilTecnico.objects.select_related("usuario").filter(
        disponible=True,
        usuario__rol=Usuario.Rol.TECNICO,
        usuario__estado=Usuario.Estado.ACTIVO,
    )
    if categoria:
        # Bloque I: la especialidad principal o una extra aprobada.
        disponibles = disponibles.filter(
            Q(especialidad=categoria)
            | Q(documentos__especialidad=categoria,
                documentos__estado=DocumentoTecnico.Estado.APROBADO),
        ).distinct()

    # Bloque H (solicitud dirigida): ?elegir=<id>.
    # - Con pendiente propia: se la diriges a ese técnico (él acepta/rechaza).
    # - Sin pendiente: vas a crearla dirigida a él.
    if "elegir" in request.GET:
        try:
            elegido_id = int(request.GET.get("elegir"))
        except (TypeError, ValueError):
            messages.error(request, "Técnico no válido.")
            return redirect("tecnicos")
        try:
            elegido = disponibles.get(usuario__pk=elegido_id)
        except PerfilTecnico.DoesNotExist:
            messages.error(request, "Ese técnico ya no está disponible.")
            return redirect("tecnicos")
        if sol_actual is None:
            return redirect(f"{reverse('solicitud_nueva')}?tecnico={elegido_id}")
        if categoria and categoria not in elegido.especialidades_efectivas:
            messages.error(
                request,
                f"{elegido.usuario.nombre_completo} no atiende esa categoría.")
            return redirect("tecnicos")
        sol_actual.tecnico = elegido.usuario
        sol_actual.save(update_fields=["tecnico"])
        request.session.pop("preseleccion", None)
        messages.success(
            request, f"Tu solicitud #{sol_actual.pk} quedó dirigida a "
                      f"{elegido.usuario.nombre_completo}: él decide si la acepta.")
        destino = reverse("tecnicos")
        if len(pendientes) > 1:
            destino += f"?solicitud={sol_actual.pk}"
        return redirect(destino)

    tarjetas = []
    for perfil in disponibles:
        km = None
        if (cliente.latitud is not None and cliente.longitud is not None
                and perfil.usuario.latitud is not None
                and perfil.usuario.longitud is not None):
            km = round(haversine_km(
                cliente.latitud, cliente.longitud,
                perfil.usuario.latitud, perfil.usuario.longitud), 1)
        tarjetas.append(_tarjeta_tecnico(perfil, km))

    orden = request.GET.get("orden", "cercania")
    if orden == "calificacion":
        tarjetas.sort(key=lambda t: (
            -(t["rating"] if t["rating"] is not None else -1),
            t["km"] is None, t["km"] or 0,
        ))
    else:
        orden = "cercania"
        tarjetas.sort(key=lambda t: (t["km"] is None, t["km"] or 0))

    # C3: posición del cliente para el mapa; fallback a Bogotá si el perfil
    # aún no tiene coordenadas (el template muestra el aviso).
    mapa_fallback = False
    if cliente.latitud is not None and cliente.longitud is not None:
        cliente_pos = {"lat": cliente.latitud, "lng": cliente.longitud,
                       "direccion": cliente.direccion}
    else:
        mapa_fallback = True
        cliente_pos = {"lat": 4.6486, "lng": -74.0628, "direccion": cliente.direccion}

    presel = request.session.get("preseleccion") or {}
    elegido_id = None
    if sol_actual is not None and presel.get("solicitud_id") == sol_actual.pk:
        elegido_id = presel.get("tecnico_id")

    return render(request, "cliente/tecnicos.html", _ctx(
        "cliente", cliente=cliente, tecnicos=tarjetas, cliente_pos=cliente_pos,
        mapa_fallback=mapa_fallback, categoria_filtro=categoria,
        categoria_filtro_txt=_NOMBRE_CATEGORIA.get(categoria, "") if categoria else "",
        orden=orden, elegido_id=elegido_id, solicitud_actual=sol_actual,
        pendientes=pendientes))


@rol_requerido(Usuario.Rol.CLIENTE)
def sugerir_categoria(request):
    """F1: endpoint liviano GET ?texto=... → JSON con la categoría sugerida.

    Nunca falla: sin texto o sin scikit-learn responde categoria=null y el
    formulario sigue funcionando igual.
    """
    texto = (request.GET.get("texto") or "").strip()
    categoria, confianza = predecir_categoria(texto)
    return JsonResponse({
        "categoria": categoria,
        "nombre": _NOMBRE_CATEGORIA.get(categoria) if categoria else None,
        "confianza": round(confianza, 2),
        "ia_disponible": categoria is not None,
    })


@rol_requerido(Usuario.Rol.CLIENTE)
def cliente_historial(request):
    """D1 / FN-6: historial real del cliente dueño.

    Solo sus solicitudes (`cliente=request.user`), más recientes primero,
    con filtro server-side `?estado=` (valor inválido = sin filtro). Ya no
    usa datos_falsos.HISTORIAL_CLIENTE.
    """
    qs = (
        Solicitud.objects.filter(cliente=request.user)
        .select_related("tecnico", "calificacion", "pago")
        .order_by("-fecha_creacion")
    )
    estados_validos = {valor for valor, _ in Solicitud.Estado.choices}
    filtro = (request.GET.get("estado") or "").strip()
    if filtro not in estados_validos:
        filtro = ""
    else:
        qs = qs.filter(estado=filtro)
    solicitudes = list(qs)
    for solicitud in solicitudes:
        solicitud.icono = _ICONO_CATEGORIA.get(solicitud.categoria, "bi-tools")
    return render(request, "cliente/historial.html", _ctx(
        "cliente", cliente=request.user, solicitudes=solicitudes,
        filtro_estado=filtro, estados=Solicitud.Estado.choices))


def _admin_para_alerta():
    """F2: destinatario de las alertas de sentimiento.

    El QA admin@test.co si existe y está activo; si no, el primer staff
    activo; si no, el primer administrador activo.
    """
    return (
        Usuario.objects.filter(
            correo="admin@test.co", estado=Usuario.Estado.ACTIVO).first()
        or Usuario.objects.filter(
            is_staff=True, estado=Usuario.Estado.ACTIVO).order_by("pk").first()
        or Usuario.objects.filter(
            rol=Usuario.Rol.ADMINISTRADOR,
            estado=Usuario.Estado.ACTIVO).order_by("pk").first()
    )


@rol_requerido(Usuario.Rol.CLIENTE)
@require_POST
def solicitud_calificar(request, pk):
    """D3 / FN-7: calificar con POST real (estrellas 1-5 + comentario ≤300).

    Solo el dueño, solo finalizada y una sola vez (`puede_calificarse`).
    El `save()` de Calificacion recalcula el promedio del técnico y se crea
    una Notificacion para él. Un segundo POST (aunque sea doble clic) se
    bloquea: por `puede_calificarse` en el caso secuencial y por la
    restricción OneToOne (IntegrityError) en carrera.

    F2: el comentario pasa por analizar_sentimiento(); si hay alerta
    (lenguaje agresivo o 5★ con texto muy negativo) la calificación queda
    con revision_admin=True, se muestra "en revisión" en el historial del
    técnico y se avisa al admin con una Notificacion.
    """
    solicitud = get_object_or_404(
        Solicitud.objects.select_related("tecnico"), pk=pk, cliente=request.user)
    if not solicitud.puede_calificarse:
        messages.error(
            request, "Esa solicitud ya fue calificada o aún no está finalizada.")
        return redirect("cliente_historial")
    form = CalificarForm(request.POST)
    if not form.is_valid():
        messages.error(
            request, f"Revisa tu calificación: {form.errors.as_text()}")
        return redirect("cliente_historial")
    estrellas = form.cleaned_data["estrellas"]
    comentario = form.cleaned_data["comentario"] or ""
    _polaridad, alerta = analizar_sentimiento(comentario, estrellas=estrellas)
    try:
        with transaction.atomic():
            Calificacion.objects.create(
                solicitud=solicitud,
                estrellas=estrellas,
                comentario=comentario,
                revision_admin=alerta,
            )
            if solicitud.tecnico_id:
                Notificacion.objects.create(
                    usuario=solicitud.tecnico,
                    tipo=Notificacion.Tipo.CALIFICACION_RECIBIDA,
                    mensaje=f"Recibiste {estrellas}★ en tu "
                            f"solicitud #{solicitud.pk} de "
                            f"{solicitud.get_categoria_display()}.",
                    solicitud=solicitud,
                )
            if alerta:
                admin = _admin_para_alerta()
                if admin is not None:
                    Notificacion.objects.create(
                        usuario=admin,
                        tipo=Notificacion.Tipo.CALIFICACION_ALERTA,
                        mensaje=f"La calificación de la solicitud #{solicitud.pk} "
                                f"({estrellas}★) quedó en revisión por posible "
                                f"lenguaje agresivo o incongruencia.",
                        solicitud=solicitud,
                    )
    except IntegrityError:
        messages.error(request, "Esa solicitud ya fue calificada.")
        return redirect("cliente_historial")
    if alerta:
        messages.warning(
            request, "Tu calificación quedó en revisión por el administrador.")
    else:
        messages.success(request, "¡Gracias por calificar!")
    return redirect("cliente_historial")


def _codigo_confirmacion():
    """CP-FN2-12: código de 6 dígitos para confirmar el cambio de correo.

    En esta versión no hay envío real de correos: el código se muestra en
    pantalla (simulación del correo de verificación) y además se exige la
    contraseña actual, así que nadie puede reemplazar el correo sin
    confirmación explícita del dueño de la cuenta.
    """
    import random
    return f"{random.randint(100000, 999999)}"


@rol_requerido(Usuario.Rol.CLIENTE)
def cliente_perfil(request):
    """B1 / FN-2: editar perfil del cliente.

    La cédula se muestra como no editable. El cambio de correo es en dos
    pasos (CP-FN2-12): 1) el cliente propone el correo nuevo (se valida
    formato y unicidad, CP-FN2-13) y queda PENDIENTE en la sesión; 2) solo
    se reemplaza tras confirmar con el código mostrado + la contraseña
    actual. Mientras no haya confirmación, el correo actual no cambia.
    """
    pendiente = request.session.get("cambio_correo")
    if request.method == "POST":
        if request.POST.get("confirmar_correo"):
            # Paso 2: confirmación del cambio de correo pendiente.
            if not pendiente:
                messages.error(request, "No hay un cambio de correo pendiente.")
                return redirect("cliente_perfil")
            codigo = (request.POST.get("codigo") or "").strip()
            password = request.POST.get("password") or ""
            if codigo != pendiente["codigo"]:
                messages.error(request, "El código de confirmación no coincide.")
            elif not request.user.check_password(password):
                messages.error(request, "La contraseña no coincide.")
            elif Usuario.objects.filter(correo__iexact=pendiente["correo"]).exclude(
                    pk=request.user.pk).exists():
                messages.error(request, "Ese correo ya pertenece a otro usuario.")
                request.session.pop("cambio_correo", None)
            else:
                request.user.correo = pendiente["correo"]
                request.user.save(update_fields=["correo"])
                request.session.pop("cambio_correo", None)
                messages.success(request, "Correo actualizado correctamente.")
                return redirect("cliente_perfil")
            return render(request, "cliente/perfil.html", _ctx(
                "cliente", form=PerfilClienteForm(instance=request.user),
                cliente=request.user, pendiente_correo=request.session.get("cambio_correo")))
        form = PerfilClienteForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            correo_nuevo = (form.cleaned_data.get("correo_nuevo") or "").strip()
            if correo_nuevo and correo_nuevo.lower() != request.user.correo.lower():
                # Paso 1: queda pendiente; NO se reemplaza todavía.
                request.session["cambio_correo"] = {
                    "correo": correo_nuevo,
                    "codigo": _codigo_confirmacion(),
                }
                messages.info(
                    request,
                    "Para completar el cambio de correo, confirma con el código "
                    "de verificación y tu contraseña. Tu correo actual sigue activo.")
                return redirect("cliente_perfil")
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("cliente_perfil")
    else:
        form = PerfilClienteForm(instance=request.user)
    return render(request, "cliente/perfil.html", _ctx(
        "cliente", form=form, cliente=request.user,
        pendiente_correo=request.session.get("cambio_correo")))


# ---------- Técnico ----------
def _perfil_tecnico_or_403(request):
    """Devuelve el PerfilTecnico del técnico en sesión (solo dueño y activo)."""
    try:
        return request.user.perfil_tecnico
    except Usuario.perfil_tecnico.RelatedObjectDoesNotExist:
        raise PermissionDenied("No tienes un perfil técnico asociado.")


def _pendientes_para_tecnico(perfil, usuario):
    """Base común de la bandeja (FN-11) y el mapa (Bloque H).

    CP-FN11-03: un técnico con disponibilidad inactiva NO recibe solicitudes
    pendientes públicas; solo ve las dirigidas específicamente a él (para
    que pueda aceptarlas o rechazarlas). Excluye las que ya rechazó y las de
    clientes suspendidos.
    """
    filtro = Q(tecnico=usuario)
    if perfil.disponible:
        filtro |= Q(visible_tecnicos=True,
                    categoria__in=perfil.especialidades_efectivas)
    return (
        Solicitud.objects.filter(estado=Solicitud.Estado.PENDIENTE)
        .filter(filtro)
        .exclude(rechazada_por=usuario)
        .exclude(cliente__estado=Usuario.Estado.SUSPENDIDO)
        .select_related("cliente").prefetch_related("fotos")
        .order_by("-urgencia", "-fecha_creacion")
    )


@rol_requerido(Usuario.Rol.TECNICO)
def tecnico_solicitudes(request):
    """C5 / FN-11: bandeja real de pendientes de su especialidad.

    Excluye las que él ya rechazó (rechazada_por) y las de clientes
    suspendidos. Ya no usa datos_falsos.SOLICITUDES_TECNICO.
    """
    perfil = _perfil_tecnico_or_403(request)
    # Bloque H+I: ve las visibles de sus especialidades efectivas (principal +
    # extras aprobadas) MÁS las dirigidas a él aunque sean privadas.
    # Bloque H: respeta visible_tecnicos (si el cliente la apagó, no sale aquí).
    solicitudes = _pendientes_para_tecnico(perfil, request.user)
    for solicitud in solicitudes:
        solicitud.icono = _ICONO_CATEGORIA.get(solicitud.categoria, "bi-tools")
    return render(request, "tecnico/solicitudes.html", _ctx(
        "tecnico", solicitudes=solicitudes, perfil=perfil))


@rol_requerido(Usuario.Rol.TECNICO)
@require_POST
def tecnico_disponibilidad(request):
    """C4 / FN-10: el switch escribe PerfilTecnico.disponible (solo dueño)."""
    perfil = _perfil_tecnico_or_403(request)
    perfil.disponible = "disponible" in request.POST
    perfil.save(update_fields=["disponible"])
    messages.success(
        request, "Disponibilidad activada." if perfil.disponible
        else "Disponibilidad pausada. No aparecerás en las búsquedas.")
    return redirect("tecnico_solicitudes")


@rol_requerido(Usuario.Rol.TECNICO)
@require_POST
def tecnico_aceptar(request, solicitud_id):
    """C5 / FN-11: aceptar atómico (Solicitud.aceptar); carrera→error."""
    perfil = _perfil_tecnico_or_403(request)
    solicitud = get_object_or_404(Solicitud, pk=solicitud_id)
    if solicitud.categoria not in perfil.especialidades_efectivas:
        raise PermissionDenied("Esa solicitud no es de tu especialidad.")
    if solicitud.rechazada_por.filter(pk=request.user.pk).exists():
        messages.error(request, "Ya habías rechazado esta solicitud.")
        return redirect("tecnico_solicitudes")
    try:
        solicitud.aceptar(request.user)
    except ValueError:
        messages.error(request, "Otro técnico ya tomó esta solicitud.")
        return redirect("tecnico_solicitudes")
    Notificacion.objects.create(
        usuario=solicitud.cliente,
        tipo=Notificacion.Tipo.SOLICITUD_ACEPTADA,
        mensaje=f"{request.user.nombre_completo} aceptó tu solicitud "
                f"#{solicitud.pk} y ya va en curso.",
        solicitud=solicitud,
    )
    messages.success(request, f"Solicitud #{solicitud.pk} aceptada. Quedó en curso.")
    return redirect("tecnico_solicitudes")


@rol_requerido(Usuario.Rol.TECNICO)
@require_POST
def tecnico_rechazar(request, solicitud_id):
    """C5 / FN-11: rechazar solo la oculta para él (rechazada_por)."""
    _perfil_tecnico_or_403(request)
    solicitud = get_object_or_404(Solicitud, pk=solicitud_id)
    if solicitud.estado != Solicitud.Estado.PENDIENTE:
        messages.error(request, "Esa solicitud ya no está pendiente.")
        return redirect("tecnico_solicitudes")
    solicitud.rechazar(request.user)
    Notificacion.objects.create(
        usuario=request.user,
        tipo=Notificacion.Tipo.SOLICITUD_RECHAZADA,
        mensaje=f"Rechazaste la solicitud #{solicitud.pk} de "
                f"{solicitud.cliente.nombre_completo}. Ya no la verás en tu bandeja.",
        solicitud=solicitud,
    )
    messages.success(request, "Solicitud rechazada.")
    return redirect("tecnico_solicitudes")


@rol_requerido(Usuario.Rol.TECNICO)
def tecnico_finalizar(request, solicitud_id):
    """C6 / FN-12: finalizar solo el técnico asignado y solo en_curso.

    Pide MONTO MANUAL obligatorio (>0, se guarda en monto_final) + notas +
    evidencia final opcional. Crea Notificacion al cliente.
    Bloque H: si el cliente ya ofreció precio, viene precargado y se respeta
    (el técnico solo lo cambia si justifica otro valor; igual el cliente
    confirma el monto final antes de pagar).
    """
    _perfil_tecnico_or_403(request)
    solicitud = get_object_or_404(
        Solicitud.objects.select_related("cliente"), pk=solicitud_id)
    if solicitud.tecnico_id != request.user.pk:
        raise PermissionDenied("Solo el técnico asignado puede finalizarla.")
    if solicitud.estado != Solicitud.Estado.EN_CURSO:
        messages.error(request, "Solo se puede finalizar una solicitud en curso.")
        return redirect("tecnico_solicitudes")
    if request.method == "POST":
        form = FinalizarSolicitudForm(request.POST, request.FILES)
        if form.is_valid():
            datos = form.cleaned_data
            with transaction.atomic():
                solicitud.finalizar(
                    notas=datos["notas"] or "", monto_final=datos["monto"])
                if datos.get("evidencia"):
                    FotoSolicitud.objects.create(
                        solicitud=solicitud, imagen=datos["evidencia"],
                        tipo=FotoSolicitud.Tipo.FINALIZACION,
                    )
                Notificacion.objects.create(
                    usuario=solicitud.cliente,
                    tipo=Notificacion.Tipo.SOLICITUD_FINALIZADA,
                    mensaje=f"Tu solicitud #{solicitud.pk} fue finalizada. "
                            f"Monto: ${datos['monto']:,.0f}.".replace(",", "."),
                    solicitud=solicitud,
                )
            messages.success(request, f"Solicitud #{solicitud.pk} finalizada.")
            return redirect("tecnico_solicitudes")
    else:
        form = FinalizarSolicitudForm(initial=(
            {"monto": solicitud.precio_ofrecido}
            if solicitud.precio_ofrecido else None))
    return render(request, "tecnico/finalizar.html", _ctx(
        "tecnico", form=form, solicitud=solicitud))


@rol_requerido(Usuario.Rol.CLIENTE)
def solicitud_pagar(request, pk):
    """E2 / FN-17: pago SIMULADO de una solicitud finalizada (solo el dueño).

    Reglas:
    - Solo finalizada con monto_final>0; si ya tiene un Pago EXITOSO, se
      bloquea el duplicado (mensaje + redirect al historial).
    - Si el pago previo FALLÓ (o quedó pendiente), se reutiliza esa misma
      fila (OneToOne): el reintento es permitido.
    - El monto se toma de solicitud.monto_final (no se confía en el POST).
    - NUNCA se pide ni se guarda número de tarjeta/CVV: solo últimos-4
      para la demo y se guarda una referencia simulada "SIM-...".
    - Éxito → Pago.marcar_exitoso() (crea la Comision vía FN-18) +
      Notificacion PAGO_EXITOSO al cliente y al técnico.
    - Fallo → estado fallido + motivo_fallo, reintentable + Notificacion
      PAGO_FALLIDO al cliente.
    """
    solicitud = get_object_or_404(
        Solicitud.objects.select_related("tecnico", "pago"),
        pk=pk, cliente=request.user,
    )
    if solicitud.estado != Solicitud.Estado.FINALIZADA:
        messages.error(request, "Solo puedes pagar una solicitud finalizada.")
        return redirect("cliente_historial")
    if not solicitud.monto_final or solicitud.monto_final <= 0:
        messages.error(request, "Esta solicitud aún no tiene un monto para pagar.")
        return redirect("cliente_historial")
    # Bloque H (anti-abuso): sin tu aceptación del monto no hay pago.
    if not solicitud.monto_aceptado:
        messages.error(
            request, "Primero acepta el monto propuesto por el técnico en tu historial.")
        return redirect("cliente_historial")
    pago_previo = getattr(solicitud, "pago", None)
    # getattr con reverse OneToOne: si no hay fila, lanza
    # RelatedObjectDoesNotExist (subclase de AttributeError) → None.
    if pago_previo is not None and pago_previo.estado == Pago.Estado.EXITOSO:
        messages.error(request, "Esta solicitud ya fue pagada.")
        return redirect("cliente_historial")

    if request.method == "POST":
        form = PagoSimuladoForm(request.POST)
        if not form.is_valid():
            return render(request, "cliente/pago.html", _ctx(
                "cliente", cliente=request.user, solicitud=solicitud,
                pago=pago_previo, form=form))
        datos = form.cleaned_data
        with transaction.atomic():
            # Re-chequeo dentro de la transacción: bloquea el doble clic /
            # doble POST que cree un segundo pago exitoso.
            solicitud.refresh_from_db()
            actual = getattr(solicitud, "pago", None)
            if actual is not None and actual.estado == Pago.Estado.EXITOSO:
                messages.error(request, "Esta solicitud ya fue pagada.")
                return redirect("cliente_historial")
            referencia = (
                f"SIM-{datos['medio'].upper()}-SOL{solicitud.pk}"
                f"-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )
            if datos["medio"] == Pago.Medio.TARJETA:
                referencia += f"-****{datos['ultimos4']}"
            if datos["resultado"] == "exito":
                if actual is None:
                    pago = Pago.objects.create(
                        solicitud=solicitud, medio_pago=datos["medio"],
                        monto=solicitud.monto_final,
                        estado=Pago.Estado.PENDIENTE,
                    )
                else:
                    pago = actual
                    pago.medio_pago = datos["medio"]
                    pago.monto = solicitud.monto_final
                    pago.motivo_fallo = ""
                    pago.save(update_fields=["medio_pago", "monto", "motivo_fallo"])
                pago.marcar_exitoso(referencia)
                Notificacion.objects.create(
                    usuario=request.user,
                    tipo=Notificacion.Tipo.PAGO_EXITOSO,
                    mensaje=f"Pagaste ${solicitud.monto_final:,.0f} por tu "
                            f"solicitud #{solicitud.pk} ({pago.get_medio_pago_display()})."
                            .replace(",", "."),
                    solicitud=solicitud,
                )
                if solicitud.tecnico_id:
                    Notificacion.objects.create(
                        usuario=solicitud.tecnico,
                        tipo=Notificacion.Tipo.PAGO_EXITOSO,
                        mensaje=f"Recibiste el pago de ${solicitud.monto_final:,.0f} "
                                f"por la solicitud #{solicitud.pk}."
                                .replace(",", "."),
                        solicitud=solicitud,
                    )
                messages.success(
                    request, f"Pago simulado exitoso por ${solicitud.monto_final:,.0f}."
                    .replace(",", "."))
                return redirect("cliente_historial")
            # Fallo: reintentable, queda la fila en FALLIDO con su motivo.
            if actual is None:
                Pago.objects.create(
                    solicitud=solicitud, medio_pago=datos["medio"],
                    monto=solicitud.monto_final,
                    estado=Pago.Estado.FALLIDO,
                    motivo_fallo=datos["motivo"],
                    referencia_pasarela=referencia,
                )
            else:
                actual.medio_pago = datos["medio"]
                actual.monto = solicitud.monto_final
                actual.referencia_pasarela = referencia
                actual.estado = Pago.Estado.FALLIDO
                actual.motivo_fallo = datos["motivo"]
                actual.save(update_fields=[
                    "medio_pago", "monto", "referencia_pasarela",
                    "estado", "motivo_fallo",
                ])
            Notificacion.objects.create(
                usuario=request.user,
                tipo=Notificacion.Tipo.PAGO_FALLIDO,
                mensaje=(f"Tu pago de la solicitud #{solicitud.pk} falló: "
                         f"{datos['motivo']} Puedes reintentarlo.")[:255],
                solicitud=solicitud,
            )
            messages.error(
                request, f"El pago simulado falló: {datos['motivo']} Puedes reintentarlo.")
            return redirect("cliente_historial")
    else:
        form = PagoSimuladoForm()
    return render(request, "cliente/pago.html", _ctx(
        "cliente", cliente=request.user, solicitud=solicitud,
        pago=pago_previo, form=form))


@rol_requerido(Usuario.Rol.CLIENTE)
@require_POST
def solicitud_cancelar(request, pk):
    """C7: el cliente dueño cancela sus solicitudes pendiente (en_curso→403)."""
    solicitud = get_object_or_404(Solicitud, pk=pk, cliente=request.user)
    if solicitud.estado == Solicitud.Estado.EN_CURSO:
        raise PermissionDenied("No puedes cancelar una solicitud en curso.")
    try:
        solicitud.cancelar()
    except ValueError:
        messages.error(request, "Solo se puede cancelar una solicitud pendiente.")
        return redirect("cliente_historial")
    Notificacion.objects.create(
        usuario=request.user,
        tipo=Notificacion.Tipo.SOLICITUD_CANCELADA,
        mensaje=f"Cancelaste tu solicitud #{solicitud.pk} de "
                f"{solicitud.get_categoria_display()}.",
        solicitud=solicitud,
    )
    messages.success(request, f"Solicitud #{solicitud.pk} cancelada.")
    return redirect("cliente_historial")


@rol_requerido(Usuario.Rol.TECNICO)
def tecnico_historial(request):
    """D2 / FN-13: historial real del técnico (solo las propias).

    Solo solicitudes donde él es el asignado (`tecnico=request.user`) y en
    estado en_curso o finalizada, más recientes primero, con filtro
    server-side `?estado=`. La calificación recibida se muestra solo lectura
    y desde cada en_curso hay acceso a finalizar (FN-12).
    """
    perfil = _perfil_tecnico_or_403(request)
    estados_propios = [Solicitud.Estado.EN_CURSO, Solicitud.Estado.FINALIZADA]
    qs = (
        Solicitud.objects.filter(tecnico=request.user, estado__in=estados_propios)
        .select_related("cliente", "calificacion")
        .order_by("-fecha_creacion")
    )
    filtro = (request.GET.get("estado") or "").strip()
    if filtro in estados_propios:
        qs = qs.filter(estado=filtro)
    else:
        filtro = ""
    solicitudes = list(qs)
    for solicitud in solicitudes:
        solicitud.icono = _ICONO_CATEGORIA.get(solicitud.categoria, "bi-tools")
    return render(request, "tecnico/historial.html", _ctx(
        "tecnico", perfil=perfil, solicitudes=solicitudes,
        filtro_estado=filtro,         estados=[
            (Solicitud.Estado.EN_CURSO, "En curso"),
            (Solicitud.Estado.FINALIZADA, "Finalizada"),
        ]))


@rol_requerido(Usuario.Rol.TECNICO)
def tecnico_perfil(request):
    """B2 / FN-9: editar perfil del técnico.

    Solo técnicos con estado activo: el guard rol_requerido ya cierra la
    sesión de usuarios no activos (pendiente/suspendido/rechazado), así que
    aquí solo llegan activos.
    """
    usuario = request.user
    try:
        perfil = usuario.perfil_tecnico
    except Usuario.perfil_tecnico.RelatedObjectDoesNotExist:
        messages.error(request, "Tu perfil técnico no existe. Contacta a soporte.")
        return redirect("tecnico_solicitudes")
    if request.method == "POST":
        form = PerfilTecnicoForm(request.POST, request.FILES, usuario=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("tecnico_perfil")
    else:
        form = PerfilTecnicoForm(initial={
            "nombre_completo": usuario.nombre_completo,
            "telefono": usuario.telefono,
            "especialidad": perfil.especialidad,
            "ciudad": perfil.ciudad,
            "precio_referencia": perfil.precio_referencia,
            "zona_cobertura": perfil.zona_cobertura,
            "latitud": usuario.latitud,
            "longitud": usuario.longitud,
        }, usuario=usuario)
    return render(request, "tecnico/perfil.html", _ctx(
        "tecnico", form=form, tecnico=usuario, perfil=perfil))


# ---------- Administrador ----------
@admin_requerido
def admin_tecnicos(request):
    """B3 / FN-14: panel real de aprobación contra la BD.

    Ya no lee datos_falsos.TECNICOS_PENDIENTES: lista técnicos con estado
    pendiente_aprobacion (más antiguos primero) con sus datos y enlace de
    vista previa del documento_certificacion. Cada decisión crea una
    Notificacion al técnico.
    """
    if request.method == "POST":
        form = DecisionTecnicoForm(request.POST)
        if form.is_valid():
            accion = form.cleaned_data["accion"]
            motivo = form.cleaned_data["motivo"]
            try:
                tecnico = Usuario.objects.select_related("perfil_tecnico").get(
                    pk=form.cleaned_data["tecnico_id"],
                    rol=Usuario.Rol.TECNICO,
                )
            except Usuario.DoesNotExist:
                messages.error(request, "Ese técnico ya no existe.")
                return redirect("admin_tecnicos")
            if accion in ("aprobar", "rechazar", "info") and (
                    tecnico.estado != Usuario.Estado.PENDIENTE_APROBACION):
                messages.error(request, "El técnico ya no está pendiente de aprobación.")
                return redirect("admin_tecnicos")
            if accion == "reabrir":
                # Bloque G: corregir una aprobación/rechazo sin querer. Solo tiene
                # sentido si ya salió de pendiente; vuelve a pendiente con todo
                # conservado y avisa al técnico.
                if tecnico.estado == Usuario.Estado.PENDIENTE_APROBACION:
                    messages.error(request, "Ese técnico ya está pendiente de aprobación.")
                    return redirect("admin_tecnicos")
                tecnico.reabrir_revision(motivo)
                Notificacion.objects.create(
                    usuario=tecnico,
                    tipo=Notificacion.Tipo.TECNICO_REABIERTO,
                    mensaje="Tu registro volvió a revisión por el administrador. Te avisaremos la decisión.",
                )
                messages.success(
                    request, f"{tecnico.nombre_completo} volvió a pendiente de aprobación.")
                return redirect("admin_tecnicos")
            if accion == "aprobar":
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
                messages.success(request, f"{tecnico.nombre_completo} fue aprobado.")
            elif accion == "rechazar":
                tecnico.estado = Usuario.Estado.RECHAZADO
                tecnico.motivo_rechazo = motivo
                tecnico.save(update_fields=["estado", "motivo_rechazo"])
                tecnico.perfil_tecnico.disponible = False
                tecnico.perfil_tecnico.save(update_fields=["disponible"])
                Notificacion.objects.create(
                    usuario=tecnico,
                    tipo=Notificacion.Tipo.TECNICO_RECHAZADO,
                    mensaje=(f"Tu registro fue rechazado. Motivo: {motivo}")[:255],
                )
                messages.success(request, f"{tecnico.nombre_completo} fue rechazado.")
            else:  # info: sigue pendiente, la observación queda en motivo_rechazo
                tecnico.motivo_rechazo = motivo
                tecnico.save(update_fields=["motivo_rechazo"])
                Notificacion.objects.create(
                    usuario=tecnico,
                    tipo=Notificacion.Tipo.INFO_SOLICITADA,
                    mensaje=(f"El administrador necesita más información: "
                             f"{motivo}")[:255],
                )
                messages.success(request, f"Se notificó a {tecnico.nombre_completo} lo que le falta.")
            return redirect("admin_tecnicos")
        else:
            messages.error(request, f"Revisa el formulario: {form.errors.as_text()}")
            return redirect("admin_tecnicos")

    pendientes = Usuario.objects.filter(
        rol=Usuario.Rol.TECNICO, estado=Usuario.Estado.PENDIENTE_APROBACION
    ).select_related("perfil_tecnico").order_by("date_joined")
    return render(request, "admin_panel/tecnicos.html", _ctx("admin", pendientes=pendientes))


@admin_requerido
def admin_usuarios(request):
    """B4 / FN-15: suspender / reactivar clientes y técnicos con motivo obligatorio.

    Suspender usa Usuario.suspender() (fuerza disponible=False en técnicos y
    tumba sus sesiones, viene del Bloque A) y crea Notificacion al afectado.
    """
    if request.method == "POST":
        form = SuspenderUsuarioForm(request.POST)
        if form.is_valid():
            try:
                objetivo = Usuario.objects.get(pk=form.cleaned_data["usuario_id"])
            except Usuario.DoesNotExist:
                messages.error(request, "El usuario ya no existe.")
                return redirect("admin_usuarios")
            if objetivo.is_superuser or (
                objetivo.is_staff and objetivo.pk == request.user.pk
            ):
                messages.error(request, "No puedes suspender tu propia cuenta de administrador.")
                return redirect("admin_usuarios")
            accion = form.cleaned_data["accion"]
            if accion == "suspender":
                objetivo.suspender(form.cleaned_data["motivo"])
                Notificacion.objects.create(
                    usuario=objetivo,
                    tipo=Notificacion.Tipo.USUARIO_SUSPENDIDO,
                    mensaje=(f"Tu cuenta fue suspendida. "
                             f"Motivo: {form.cleaned_data['motivo']}")[:255],
                )
                messages.success(request, f"{objetivo.nombre_completo} fue suspendido.")
            else:
                objetivo.reactivar()
                messages.success(request, f"{objetivo.nombre_completo} fue reactivado.")
            return redirect("admin_usuarios")
        else:
            messages.error(request, f"Revisa el formulario: {form.errors.as_text()}")
            return redirect("admin_usuarios")

    usuarios = Usuario.objects.filter(
        rol__in=[Usuario.Rol.CLIENTE, Usuario.Rol.TECNICO]
    ).select_related("perfil_tecnico").order_by("-date_joined")
    return render(request, "admin_panel/usuarios.html", _ctx("admin", usuarios=usuarios))


@admin_requerido
def admin_reportes(request):
    """E4 / FN-16: dashboard de reportes, solo lectura (GET).

    - Servicios finalizados (count, en el rango).
    - Técnicos activos (count, global: rol técnico + estado activo).
    - Suma de comisiones en el rango (?desde=&hasta= YYYY-MM-DD,
      default últimos 30 días) + total pagado y nº de pagos exitosos.
    - Usuarios activos / suspendidos (counts globales).
    Todo se calcula con agregados directos en BD (SUM/COUNT).
    """
    from datetime import datetime, timedelta

    hoy = timezone.localdate()
    por_defecto_desde = hoy - timedelta(days=30)

    def _parse_fecha(valor, respaldo):
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return respaldo

    desde = _parse_fecha(request.GET.get("desde"), por_defecto_desde)
    hasta = _parse_fecha(request.GET.get("hasta"), hoy)
    if desde > hasta:
        desde, hasta = hasta, desde

    # Límites como fecha-hora (no lookups __date): MySQL sin las tablas de
    # zonas horarias hace que CONVERT_TZ devuelva NULL y los filtros __date
    # descarten todas las filas (reportes siempre en cero).
    inicio = timezone.make_aware(datetime.combine(desde, datetime.min.time()))
    fin = timezone.make_aware(
        datetime.combine(hasta + timedelta(days=1), datetime.min.time()))

    finalizadas = Solicitud.objects.filter(
        estado=Solicitud.Estado.FINALIZADA,
        fecha_finalizacion__gte=inicio,
        fecha_finalizacion__lt=fin,
    )
    comisiones = Comision.objects.filter(
        fecha_calculo__gte=inicio, fecha_calculo__lt=fin
    )
    pagos_ok = Pago.objects.filter(
        estado=Pago.Estado.EXITOSO,
        fecha_creacion__gte=inicio, fecha_creacion__lt=fin,
    )
    total_comisiones = comisiones.aggregate(total=Sum("monto_comision"))["total"] or 0
    total_pagado = pagos_ok.aggregate(total=Sum("monto"))["total"] or 0

    contexto = {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "porcentaje_actual": ConfiguracionComision.actual().porcentaje,
        "servicios_finalizados": finalizadas.count(),
        "comisiones_suma": total_comisiones,
        "comisiones_cantidad": comisiones.count(),
        "pagos_exitosos": pagos_ok.count(),
        "pagos_total": total_pagado,
        "tecnicos_activos": Usuario.objects.filter(
            rol=Usuario.Rol.TECNICO, estado=Usuario.Estado.ACTIVO).count(),
        "tecnicos_disponibles": PerfilTecnico.objects.filter(
            disponible=True, usuario__estado=Usuario.Estado.ACTIVO).count(),
        "usuarios_activos": Usuario.objects.filter(
            estado=Usuario.Estado.ACTIVO).count(),
        "usuarios_suspendidos": Usuario.objects.filter(
            estado=Usuario.Estado.SUSPENDIDO).count(),
    }
    return render(request, "admin_panel/reportes.html", _ctx("admin", **contexto))


# ---------- Notificaciones (FN-19) ----------
def _rol_ctx(usuario):
    """El rol para base.html: el admin ve su nav aunque su rol sea otro."""
    if usuario.is_staff or usuario.is_superuser:
        return "admin"
    return usuario.rol


@rol_requerido(Usuario.Rol.CLIENTE, Usuario.Rol.TECNICO, Usuario.Rol.ADMINISTRADOR)
def notificaciones(request):
    """D4 / FN-19: lista propia de notificaciones, más recientes primero."""
    notifs = (
        Notificacion.objects.filter(usuario=request.user)
        .select_related("solicitud")
        .order_by("-fecha_creacion")
    )
    return render(request, "notificaciones.html", _ctx(
        _rol_ctx(request.user), cliente=request.user, notificaciones=list(notifs)))


@rol_requerido(Usuario.Rol.CLIENTE, Usuario.Rol.TECNICO, Usuario.Rol.ADMINISTRADOR)
@require_POST
def notificacion_leer(request, pk):
    """D4 / FN-19: marcar como leída una notificación propia."""
    notif = get_object_or_404(Notificacion, pk=pk, usuario=request.user)
    if not notif.leida:
        notif.leida = True
        notif.save(update_fields=["leida"])
    return redirect("notificaciones")


# ---------- Bloque G: ficha, reseñas, documentos y baja voluntaria ----------

def _ficha_tecnico(usuario):
    """Datos agregados de un técnico para la ficha admin y el perfil público."""
    perfil = usuario.perfil_tecnico
    reseñas = (
        Calificacion.objects.filter(solicitud__tecnico=usuario, oculta=False)
        .select_related("solicitud")
        .order_by("-fecha_creacion")
    )
    return {
        "tecnico": usuario,
        "perfil": perfil,
        "documentos": list(perfil.documentos.all()),
        "resenas": list(reseñas),
        "n_finalizadas": Solicitud.objects.filter(
            tecnico=usuario, estado=Solicitud.Estado.FINALIZADA).count(),
        "n_en_curso": Solicitud.objects.filter(
            tecnico=usuario, estado=Solicitud.Estado.EN_CURSO).count(),
    }


@admin_requerido
def admin_ficha_tecnico(request, pk):
    """Bloque G: ficha completa del técnico para revisar (cualquier estado).

    El admin ve datos, perfil, documento principal + extras, historial de
    solicitudes y reseñas. Desde aquí también decide (aprobar/rechazar/info)
    o reabre la revisión si ya había decidido.
    """
    tecnico = get_object_or_404(
        Usuario.objects.select_related("perfil_tecnico"),
        pk=pk, rol=Usuario.Rol.TECNICO,
    )
    return render(request, "admin_panel/ficha_tecnico.html", _ctx(
        "admin", form_decision=DecisionTecnicoForm(), **_ficha_tecnico(tecnico)))


@admin_requerido
def admin_resenas(request):
    """Bloque G: moderación de reseñas (?filtro=todas|revision|ocultas)."""
    filtro = request.GET.get("filtro", "todas")
    resenas = Calificacion.objects.select_related(
        "solicitud", "solicitud__cliente", "solicitud__tecnico",
    ).order_by("-fecha_creacion")
    if filtro == "revision":
        resenas = resenas.filter(revision_admin=True, oculta=False)
    elif filtro == "ocultas":
        resenas = resenas.filter(oculta=True)
    else:
        filtro = "todas"
    return render(request, "admin_panel/resenas.html", _ctx(
        "admin", resenas=list(resenas), filtro=filtro,
        form_moderar=ResenaModerarForm()))


@admin_requerido
@require_POST
def resena_moderar(request):
    """Bloque G: ocultar/mostrar una reseña (recalcula el promedio solo).

    Bloque J: 'revisada' quita la etiqueta cuando el admin ya la revisó y la
    considera válida (sigue visible y contando).
    """
    form = ResenaModerarForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Revisa el formulario: {form.errors.as_text()}")
        return redirect("admin_resenas")
    resena = get_object_or_404(Calificacion, pk=form.cleaned_data["resena_id"])
    accion = form.cleaned_data["accion"]
    if accion == "revisada":
        resena.revision_admin = False
        resena.save(update_fields=["revision_admin"])
        messages.success(request, "Reseña marcada como revisada: queda visible.")
        return redirect("admin_resenas")
    ocultar = accion == "ocultar"
    resena.set_oculta(ocultar)
    messages.success(
        request,
        f"Reseña de {resena.solicitud.cliente.nombre_completo} "
        f"{'ocultada: ya no cuenta en el promedio.' if ocultar else 'visible de nuevo.'}")
    return redirect("admin_resenas")


@rol_requerido(Usuario.Rol.CLIENTE)
def tecnico_publico(request, pk):
    """Bloque G: "¿confío en él?" — ficha pública del técnico con reseñas.

    Solo técnicos activos; las reseñas ocultas por moderación no se muestran.
    """
    tecnico = get_object_or_404(
        Usuario.objects.select_related("perfil_tecnico"),
        pk=pk, rol=Usuario.Rol.TECNICO, estado=Usuario.Estado.ACTIVO,
    )
    return render(request, "cliente/tecnico_detalle.html", _ctx(
        "cliente", cliente=request.user, **_ficha_tecnico(tecnico)))


@rol_requerido(Usuario.Rol.TECNICO)
def documento_agregar(request):
    """Bloque G: el técnico suma un certificado extra (nombre + archivo)."""
    perfil = _perfil_tecnico_or_403(request)
    if request.method == "POST":
        form = DocumentoTecnicoForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.perfil = perfil
            doc.save()
            messages.success(request, f"Documento '{doc.nombre}' agregado.")
            return redirect("tecnico_perfil")
        messages.error(request, f"Revisa el documento: {form.errors.as_text()}")
        return redirect("tecnico_perfil")
    return redirect("tecnico_perfil")


@rol_requerido(Usuario.Rol.TECNICO)
@require_POST
def documento_eliminar(request, pk):
    """Bloque G: el técnico borra uno de sus certificados extra (solo suyos)."""
    _perfil_tecnico_or_403(request)
    doc = get_object_or_404(DocumentoTecnico, pk=pk, perfil__usuario=request.user)
    nombre = doc.nombre
    doc.archivo.delete(save=False)
    doc.delete()
    messages.success(request, f"Documento '{nombre}' eliminado.")
    return redirect("tecnico_perfil")


@rol_requerido(Usuario.Rol.TECNICO)
def tecnico_mapa(request):
    """Bloque H: el mapa de clientes — solicitudes visibles en Leaflet.

    Espejo de /cliente/tecnicos/ pero al revés: el técnico ve solicitudes
    pendientes visibles de sus especialidades efectivas (o dirigidas a él),
    con la posición del cliente, lo ofrecido y aceptar/rechazar.
    """
    perfil = _perfil_tecnico_or_403(request)
    base = _pendientes_para_tecnico(perfil, request.user)
    yo = request.user
    tarjetas = []
    for s in base:
        km = None
        if (yo.latitud is not None and yo.longitud is not None
                and s.cliente.latitud is not None
                and s.cliente.longitud is not None):
            km = round(haversine_km(
                yo.latitud, yo.longitud,
                s.cliente.latitud, s.cliente.longitud), 1)
        tarjetas.append({
            "id": s.pk,
            "cliente": s.cliente.nombre_completo,
            "categoria": s.get_categoria_display(),
            "icono": _ICONO_CATEGORIA.get(s.categoria, "bi-tools"),
            "descripcion": s.descripcion,
            "direccion": s.direccion,
            "urgencia": s.get_urgencia_display(),
            "fecha": s.fecha_creacion,
            "precio_txt": (
                f"${s.precio_ofrecido:,.0f}".replace(",", ".")
                if s.precio_ofrecido else "a convenir"),
            "dirigida": s.tecnico_id == yo.pk,
            "lat": s.cliente.latitud,
            "lng": s.cliente.longitud,
            "km": km,
        })
    if yo.latitud is not None and yo.longitud is not None:
        yo_pos = {"lat": yo.latitud, "lng": yo.longitud}
        mapa_fallback = False
    else:
        yo_pos = {"lat": 4.6486, "lng": -74.0628}
        mapa_fallback = True
    return render(request, "tecnico/mapa.html", _ctx(
        "tecnico", solicitudes=tarjetas, yo_pos=yo_pos,
        mapa_fallback=mapa_fallback))


@rol_requerido(Usuario.Rol.CLIENTE)
@require_POST
def solicitud_precio(request, pk):
    """Bloque H: el dueño ajusta precio ofrecido/visibilidad en su pendiente."""
    solicitud = get_object_or_404(
        Solicitud, pk=pk, cliente=request.user,
        estado=Solicitud.Estado.PENDIENTE)
    form = PrecioEditarForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Revisa el precio: {form.errors.as_text()}")
        return redirect("cliente_historial")
    solicitud.precio_ofrecido = form.cleaned_data["precio_ofrecido"]
    solicitud.visible_tecnicos = bool(form.cleaned_data["visible_tecnicos"])
    solicitud.save(update_fields=["precio_ofrecido", "visible_tecnicos"])
    messages.success(request, f"Precio de tu solicitud #{solicitud.pk} actualizado.")
    return redirect("cliente_historial")


@rol_requerido(Usuario.Rol.CLIENTE)
@require_POST
def monto_decidir(request):
    """Bloque H (anti-abuso): aceptar el monto habilita pagar; rechazarlo
    devuelve la solicitud a en curso para que el técnico lo ajuste."""
    form = MontoDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Revisa el formulario: {form.errors.as_text()}")
        return redirect("cliente_historial")
    solicitud = get_object_or_404(
        Solicitud, pk=form.cleaned_data["solicitud_id"],
        cliente=request.user, estado=Solicitud.Estado.FINALIZADA)
    if not solicitud.monto_final:
        messages.error(request, "Esa solicitud aún no tiene monto propuesto.")
        return redirect("cliente_historial")
    if form.cleaned_data["accion"] == "aceptar_monto":
        solicitud.confirmar_monto()
        messages.success(
            request, f"Monto aceptado. Ya puedes pagar tu solicitud #{solicitud.pk}.")
    else:
        solicitud.rechazar_monto()
        if solicitud.tecnico_id:
            Notificacion.objects.create(
                usuario=solicitud.tecnico,
                tipo=Notificacion.Tipo.SOLICITUD_RECHAZADA,
                mensaje=f"El cliente rechazó tu monto de la solicitud #{solicitud.pk}: "
                        f"volvió a en curso para que lo ajustes.",
                solicitud=solicitud,
            )
        messages.success(
            request, f"Monto rechazado: la solicitud #{solicitud.pk} volvió a en curso.")
    return redirect("cliente_historial")


@admin_requerido
def admin_ia(request):
    """Bloque D: tablero de aprendizaje (lámina de sustentación).

    Muestra cuántas muestras dejó el uso, el % de acierto de la IA y las
    confusiones top (sugerida → elegida). Solo lectura + botón reentrenar.
    """
    from django.db.models import Count

    from core.ia import EJEMPLOS, reiniciar_modelo

    if request.method == "POST":
        reiniciar_modelo()
        messages.success(
            request, "Modelo reiniciado: la próxima sugerencia ya incluye lo aprendido.")
        return redirect("admin_ia")
    total = IASugerencia.objects.count()
    con_sug = IASugerencia.objects.exclude(categoria_sugerida__isnull=True)
    aciertos = con_sug.filter(acierto=True).count()
    precision = round(100 * aciertos / con_sug.count(), 1) if con_sug.exists() else None
    por_categoria = list(
        IASugerencia.objects.exclude(categoria_final__isnull=True)
        .values("categoria_final").annotate(n=Count("pk")).order_by("-n"))
    confusiones = list(
        IASugerencia.objects.exclude(categoria_sugerida__isnull=True)
        .exclude(categoria_final__isnull=True)
        .exclude(categoria_sugerida=F("categoria_final"))
        .values("categoria_sugerida", "categoria_final")
        .annotate(n=Count("pk")).order_by("-n")[:10])
    return render(request, "admin_panel/ia.html", _ctx(
        "admin", total=total, precision=precision,
        frases_base=len(EJEMPLOS), por_categoria=por_categoria,
        confusiones=confusiones))


@admin_requerido
@require_POST
def documento_decidir(request):
    """Bloque I: aprobar/rechazar una habilidad postulada (con motivo)."""
    form = DocumentoDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Revisa el formulario: {form.errors.as_text()}")
        return redirect("admin_tecnicos")
    doc = get_object_or_404(
        DocumentoTecnico.objects.select_related("perfil", "perfil__usuario"),
        pk=form.cleaned_data["documento_id"])
    if form.cleaned_data["accion"] == "aprobar_doc":
        doc.estado = DocumentoTecnico.Estado.APROBADO
        doc.motivo = ""
        mensaje = (f"Tu habilidad '{doc.nombre}' fue aprobada: ya cuenta "
                   f"para que te encuentren en esa categoría.")
    else:
        doc.estado = DocumentoTecnico.Estado.RECHAZADO
        doc.motivo = (form.cleaned_data["motivo"] or "").strip()
        mensaje = f"Tu habilidad '{doc.nombre}' fue rechazada. Motivo: {doc.motivo}"
    doc.save(update_fields=["estado", "motivo"])
    Notificacion.objects.create(
        usuario=doc.perfil.usuario,
        tipo=(Notificacion.Tipo.TECNICO_APROBADO
              if doc.estado == DocumentoTecnico.Estado.APROBADO
              else Notificacion.Tipo.TECNICO_RECHAZADO),
        mensaje=mensaje,
    )
    messages.success(request, f"Habilidad '{doc.nombre}': {doc.get_estado_display().lower()}.")
    return redirect("admin_ficha_tecnico", pk=doc.perfil.usuario.pk)


@rol_requerido(Usuario.Rol.CLIENTE, Usuario.Rol.TECNICO)
def cuenta_desactivar(request):
    """Bloque G: baja voluntaria. Pide la contraseña como confirmación.

    Pasa a INACTIVO (sin login), fuerza disponible=False y tumba sesiones.
    El admin la revierte con reactivar(); los datos e historial se conservan.
    """
    usuario = request.user
    if request.method == "POST":
        form = DesactivarCuentaForm(request.POST, usuario=usuario)
        if form.is_valid():
            usuario.desactivar()
            Notificacion.objects.create(
                usuario=usuario,
                tipo=Notificacion.Tipo.CUENTA_DESACTIVADA,
                mensaje="Desactivaste tu cuenta. Contáctanos si quieres reactivarla.",
            )
            logout(request)
            messages.success(request, "Tu cuenta fue desactivada correctamente.")
            return redirect("landing")
    else:
        form = DesactivarCuentaForm(usuario=usuario)
    rol = "cliente" if usuario.rol == Usuario.Rol.CLIENTE else "tecnico"
    return render(request, "publico/desactivar_cuenta.html", _ctx(rol, form=form))
