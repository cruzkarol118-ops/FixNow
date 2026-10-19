import re
from datetime import date

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    Categoria, DocumentoTecnico, Pago, PerfilTecnico, Solicitud, Usuario,
)
from .validators import validar_certificacion, validar_foto, validar_nombre, validar_telefono

ATRS_TEXTO = "form-control"
ATRS_CHECK = "form-check-input"


def _campo_password(id_campo):
    """Comparte el widget entre FN-1 y FN-8 sin repetir el bloque completo."""
    return forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": ATRS_TEXTO, "id": id_campo, "autocomplete": "new-password",
        }),
    )


def _campo_password2(id_campo):
    return forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            "class": ATRS_TEXTO, "id": id_campo, "autocomplete": "new-password",
        }),
    )


def _campo_terminos(id_campo):
    return forms.BooleanField(
        label="Acepto los términos y condiciones",
        error_messages={"required": "Debes aceptar los términos para continuar."},
        widget=forms.CheckboxInput(attrs={"class": ATRS_CHECK, "id": id_campo}),
    )


def _validar_coords(datos):
    """Ubicación por mapa: ambas coordenadas o ninguna, dentro de rango válido."""
    lat, lng = datos.get("latitud"), datos.get("longitud")
    if (lat is None) != (lng is None):
        raise ValidationError(
            "Marca tu ubicación completa en el mapa (o déjala vacía).")
    if lat is not None and not (-90 <= lat <= 90):
        raise ValidationError("Latitud fuera de rango.")
    if lng is not None and not (-180 <= lng <= 180):
        raise ValidationError("Longitud fuera de rango.")


def _validar_politica_password(password):
    """FN-1/FN-8: mínimo 8 caracteres, una mayúscula, un número y un símbolo."""
    errores = []
    if len(password) < 8:
        errores.append("Debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        errores.append("Debe incluir al menos una mayúscula.")
    if not re.search(r"\d", password):
        errores.append("Debe incluir al menos un número.")
    if not re.search(r"[^A-Za-z0-9]", password):
        errores.append("Debe incluir al menos un símbolo (por ejemplo ! # $ %).")
    if errores:
        raise ValidationError(errores)


class RegistroClienteForm(forms.ModelForm):
    """
    FN-1: registro de cliente. Los campos de Meta.fields ya traen su
    validación desde el modelo (cedula con regex de 6-10 dígitos, correo
    único, etc.) porque ModelForm llama a full_clean() del modelo solo.
    Contraseña y términos no son campos del modelo, así que se agregan
    aparte y se validan aquí.
    """

    password = _campo_password("password")
    password2 = _campo_password2("password2")
    terminos = _campo_terminos("terminos")

    class Meta:
        model = Usuario
        fields = ["cedula", "nombre_completo", "correo", "telefono"]
        widgets = {
            "cedula": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "cedula", "inputmode": "numeric",
                "maxlength": "10", "minlength": "6", "pattern": "[0-9]*",
                "data-filtrar": "digitos", "autocomplete": "off",
            }),
            "nombre_completo": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "nombre_completo", "autocomplete": "name",
                "data-filtrar": "letras",
            }),
            "correo": forms.EmailInput(attrs={
                "class": ATRS_TEXTO, "id": "correo", "autocomplete": "email",
            }),
            "telefono": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "telefono", "autocomplete": "tel",
                "data-filtrar": "telefono",
            }),
        }
        error_messages = {
            "cedula": {"unique": "Ya existe una cuenta registrada con esta cédula."},
            "correo": {"unique": "Ya existe una cuenta registrada con este correo."},
        }

    def clean_password(self):
        password = self.cleaned_data["password"]
        _validar_politica_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.rol = Usuario.Rol.CLIENTE
        usuario.estado = Usuario.Estado.ACTIVO
        usuario.set_password(self.cleaned_data["password"])
        if commit:
            usuario.save()
        return usuario


class RegistroTecnicoForm(forms.ModelForm):
    """
    FN-8: a diferencia de FN-1, junta datos de dos modelos (Usuario y
    PerfilTecnico) en un solo formulario, y el usuario queda con estado
    'pendiente_aprobacion' en vez de quedar activo de una vez (ver FN-14).
    """

    especialidad = forms.ChoiceField(
        label="Especialidad",
        choices=[("", "Elige una")] + list(Categoria.choices),
        widget=forms.Select(attrs={"class": "form-select", "id": "especialidad"}),
    )
    ciudad = forms.CharField(
        label="Ciudad",
        widget=forms.TextInput(attrs={"class": ATRS_TEXTO, "id": "ciudad"}),
    )
    documento_certificacion = forms.FileField(
        label="Documento de certificación",
        validators=[validar_certificacion],
        error_messages={"required": "Adjunta tu certificación para poder registrarte."},
        widget=forms.ClearableFileInput(attrs={
            "class": ATRS_TEXTO, "id": "certificacion", "accept": "application/pdf,image/*",
        }),
    )
    password = _campo_password("password")
    password2 = _campo_password2("password2")
    terminos = _campo_terminos("terminos")

    class Meta:
        model = Usuario
        fields = ["cedula", "nombre_completo", "correo", "telefono"]
        widgets = {
            "cedula": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "cedula", "inputmode": "numeric",
                "maxlength": "10", "minlength": "6", "pattern": "[0-9]*",
                "data-filtrar": "digitos", "autocomplete": "off",
            }),
            "nombre_completo": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "nombre_completo", "autocomplete": "name",
                "data-filtrar": "letras",
            }),
            "correo": forms.EmailInput(attrs={
                "class": ATRS_TEXTO, "id": "correo", "autocomplete": "email",
            }),
            "telefono": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "telefono", "autocomplete": "tel",
                "data-filtrar": "telefono",
            }),
        }
        error_messages = {
            "cedula": {"unique": "Ya existe una cuenta registrada con esta cédula."},
            "correo": {"unique": "Ya existe una cuenta registrada con este correo."},
        }

    def clean_password(self):
        password = self.cleaned_data["password"]
        _validar_politica_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.rol = Usuario.Rol.TECNICO
        usuario.estado = Usuario.Estado.PENDIENTE_APROBACION
        usuario.set_password(self.cleaned_data["password"])
        if commit:
            # Si falla la creación del perfil, no debe quedar un Usuario
            # huérfano sin PerfilTecnico asociado.
            with transaction.atomic():
                usuario.save()
                PerfilTecnico.objects.create(
                    usuario=usuario,
                    especialidad=self.cleaned_data["especialidad"],
                    ciudad=self.cleaned_data["ciudad"],
                    documento_certificacion=self.cleaned_data["documento_certificacion"],
                )
        return usuario


class CambioPasswordForm(PasswordChangeForm):
    """Bloque A5: cambio de contraseña exigiendo la actual + política FixNow.

    PasswordChangeForm ya valida la contraseña actual (old_password) y que
    las dos nuevas coincidan; aquí se suma la política del proyecto
    (mínimo 8, mayúscula, número y símbolo) y los estilos Bootstrap.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("old_password", "new_password1", "new_password2"):
            clases = self.fields[campo].widget.attrs.get("class", "")
            self.fields[campo].widget.attrs["class"] = f"{clases} form-control".strip()

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        if password:
            _validar_politica_password(password)
        return password


class PerfilClienteForm(forms.ModelForm):
    """B1 / FN-2: el cliente edita nombre, teléfono, dirección y fecha de nacimiento.

    La cédula NO es editable (se muestra como solo lectura en el template).
    El correo tampoco se reemplaza directamente: si el cliente digita un
    `correo_nuevo`, la vista exige una confirmación (código + contraseña)
    antes de reemplazarlo (CP-FN2-12/13).
    La dirección es obligatoria: FN-3 la exige para crear solicitudes.
    """

    correo_nuevo = forms.EmailField(
        label="Nuevo correo (opcional)", required=False,
        help_text="Si lo diligencias, te pediremos confirmar el cambio antes de aplicarlo.",
        widget=forms.EmailInput(attrs={
            "class": ATRS_TEXTO, "id": "correo_nuevo", "autocomplete": "email",
        }),
    )

    class Meta:
        model = Usuario
        fields = ["nombre_completo", "telefono", "direccion", "fecha_nacimiento",
                  "latitud", "longitud"]
        widgets = {
            "nombre_completo": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "nombre_completo", "autocomplete": "name",
                "data-filtrar": "letras",
            }),
            "telefono": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "telefono", "autocomplete": "tel",
                "data-filtrar": "telefono",
            }),
            "direccion": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "direccion", "autocomplete": "street-address",
            }),
            "fecha_nacimiento": forms.DateInput(attrs={
                "class": ATRS_TEXTO, "id": "fecha_nacimiento", "type": "date",
                "data-max-hoy": "1",
            }),
            # La ubicación se elige en el mapa del perfil (selector visual);
            # el usuario nunca digita coordenadas.
            "latitud": forms.HiddenInput(attrs={"id": "id_latitud"}),
            "longitud": forms.HiddenInput(attrs={"id": "id_longitud"}),
        }

    def clean(self):
        datos = super().clean()
        _validar_coords(datos)
        return datos

    def clean_correo_nuevo(self):
        """CP-FN2-13: el correo nuevo no puede pertenecer a otro usuario."""
        correo = (self.cleaned_data.get("correo_nuevo") or "").strip()
        if correo and Usuario.objects.filter(correo__iexact=correo).exclude(
                pk=self.instance.pk).exists():
            raise ValidationError(
                "Ya existe una cuenta registrada con este correo.")
        return correo

    def clean_direccion(self):
        direccion = (self.cleaned_data.get("direccion") or "").strip()
        if not direccion:
            raise ValidationError(
                "La dirección es obligatoria: la necesitarás para crear solicitudes."
            )
        return direccion

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get("fecha_nacimiento")
        if fecha and fecha > date.today():
            raise ValidationError("La fecha de nacimiento no puede ser futura.")
        return fecha


class PerfilTecnicoForm(forms.Form):
    """B2 / FN-9: edita Usuario (nombre, teléfono) + PerfilTecnico
    (especialidad, ciudad, precio, zona, foto) en un solo formulario.

    Cédula, correo, rol, estado y promedio NO son editables.
    """

    nombre_completo = forms.CharField(
        label="Nombre completo", max_length=100,
        validators=[validar_nombre],
        error_messages={
            "required": "El nombre es obligatorio.",
            "max_length": "El nombre no puede pasar de 100 caracteres.",
        },
        widget=forms.TextInput(attrs={
            "class": ATRS_TEXTO, "id": "nombre_completo",
            "data-filtrar": "letras"}),
    )
    telefono = forms.CharField(
        label="Teléfono", max_length=20,
        validators=[validar_telefono],
        error_messages={"required": "El teléfono es obligatorio."},
        widget=forms.TextInput(attrs={
            "class": ATRS_TEXTO, "id": "telefono",
            "data-filtrar": "telefono"}),
    )
    especialidad = forms.ChoiceField(
        label="Especialidad", choices=Categoria.choices,
        widget=forms.Select(attrs={"class": "form-select", "id": "especialidad"}),
    )
    ciudad = forms.CharField(
        label="Ciudad", max_length=100,
        widget=forms.TextInput(attrs={"class": ATRS_TEXTO, "id": "ciudad"}),
    )
    precio_referencia = forms.DecimalField(
        label="Precio de referencia", max_digits=10, decimal_places=0,
        required=False,
        help_text="Déjalo vacío para mostrar “a convenir”.",
        widget=forms.NumberInput(attrs={"class": ATRS_TEXTO, "id": "precio_referencia", "min": "1"}),
    )
    zona_cobertura = forms.CharField(
        label="Zona de cobertura", max_length=255,
        error_messages={"required": "La zona de cobertura es obligatoria."},
        widget=forms.TextInput(attrs={"class": ATRS_TEXTO, "id": "zona_cobertura"}),
    )
    foto_perfil = forms.ImageField(
        label="Foto de perfil", required=False, validators=[validar_foto],
        widget=forms.ClearableFileInput(attrs={"class": ATRS_TEXTO, "id": "foto_perfil", "accept": "image/*"}),
    )
    # Ubicación por mapa (selector visual; el usuario nunca digita coords).
    latitud = forms.FloatField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_latitud"}))
    longitud = forms.FloatField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_longitud"}))

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_precio_referencia(self):
        """CP-FN9-03/04: el precio, si se define, debe ser mayor que cero."""
        precio = self.cleaned_data.get("precio_referencia")
        if precio is not None and precio <= 0:
            raise ValidationError("El precio no puede ser cero ni negativo.")
        return precio

    def clean(self):
        datos = super().clean()
        _validar_coords(datos)
        return datos

    def save(self):
        datos = self.cleaned_data
        usuario = self.usuario
        usuario.nombre_completo = datos["nombre_completo"].strip()
        usuario.telefono = datos["telefono"].strip()
        usuario.latitud = datos.get("latitud")
        usuario.longitud = datos.get("longitud")
        usuario.save(update_fields=["nombre_completo", "telefono", "latitud", "longitud"])
        perfil = usuario.perfil_tecnico
        perfil.especialidad = datos["especialidad"]
        perfil.ciudad = datos["ciudad"].strip()
        perfil.precio_referencia = datos["precio_referencia"]
        perfil.zona_cobertura = (datos["zona_cobertura"] or "").strip()
        if datos.get("foto_perfil"):
            perfil.foto_perfil = datos["foto_perfil"]
        perfil.save(update_fields=[
            "especialidad", "ciudad", "precio_referencia",
            "zona_cobertura", "foto_perfil",
        ])
        return usuario


class SolicitudNuevaForm(forms.Form):
    """C1 / FN-3: validación escalar de la solicitud.

    Las fotos se validan aparte en la vista (getlist + validar_foto) porque
    son de 0 a 3 archivos, no un solo campo.
    """

    categoria = forms.ChoiceField(
        choices=Categoria.choices,
        error_messages={"invalid_choice": "Elige una categoría válida."},
    )
    descripcion = forms.CharField(
        min_length=10, max_length=300, strip=True,
        error_messages={
            "min_length": "Describe el problema con al menos 10 caracteres.",
            "max_length": "La descripción no puede pasar de 300 caracteres.",
            "required": "Describe el problema con al menos 10 caracteres.",
        },
    )
    direccion = forms.CharField(
        max_length=255, strip=True,
        error_messages={"required": "Escribe la dirección donde se hará el servicio."},
    )
    urgencia = forms.ChoiceField(
        choices=Solicitud.Urgencia.choices,
        error_messages={"invalid_choice": "Urgencia no válida."},
    )
    # Bloque H: lo que el cliente ofrece pagar (vacío = lo pone el técnico).
    precio_ofrecido = forms.DecimalField(
        label="Precio que ofreces (opcional)", max_digits=10, decimal_places=0,
        min_value=1, required=False,
        help_text="Si lo dejas vacío, el técnico propone el precio al finalizar.",
        error_messages={"min_value": "El precio ofrecido debe ser mayor que cero."},
        widget=forms.NumberInput(attrs={"class": ATRS_TEXTO, "id": "precio_ofrecido", "min": "1"}),
    )
    # Bloque H: apagada = privada (no sale en el mapa de técnicos, eliges tú).
    visible_tecnicos = forms.BooleanField(
        label="Visible para técnicos (la verán en su mapa y podrán ofrecerse)",
        required=False, initial=True,
        widget=forms.CheckboxInput(attrs={"class": ATRS_CHECK, "id": "visible_tecnicos"}),
    )


class FinalizarSolicitudForm(forms.Form):
    """C6 / FN-12: monto manual obligatorio + notas + evidencia final opcional."""

    monto = forms.DecimalField(
        label="Monto del servicio", min_value=1, max_digits=10, decimal_places=0,
        error_messages={
            "required": "El monto es obligatorio: digita lo que le cobrarás al cliente.",
            "min_value": "El monto debe ser mayor que cero.",
        },
        widget=forms.NumberInput(attrs={"class": ATRS_TEXTO, "id": "monto", "min": "1"}),
    )
    notas = forms.CharField(
        label="Notas de finalización", max_length=300, required=False, strip=True,
        widget=forms.Textarea(attrs={
            "class": ATRS_TEXTO, "id": "notas", "rows": 3, "maxlength": "300",
        }),
    )
    evidencia = forms.FileField(
        label="Foto de evidencia final", required=False, validators=[validar_foto],
        widget=forms.ClearableFileInput(attrs={
            "class": ATRS_TEXTO, "id": "evidencia", "accept": "image/jpeg,image/png",
        }),
    )


class CalificarForm(forms.Form):
    """D3 / FN-7: estrellas 1-5 obligatorias + comentario opcional ≤300.

    La unicidad (una sola vez por solicitud) no se valida aquí sino en la
    vista con Solicitud.puede_calificarse + la restricción OneToOne.
    """

    estrellas = forms.IntegerField(
        min_value=1, max_value=5,
        error_messages={
            "required": "Elige de 1 a 5 estrellas.",
            "min_value": "La calificación mínima es 1 estrella.",
            "max_value": "La calificación máxima es 5 estrellas.",
            "invalid": "Elige de 1 a 5 estrellas.",
        },
        widget=forms.HiddenInput(attrs={"id": "notaInput"}),
    )
    comentario = forms.CharField(
        max_length=300, required=False, strip=True,
        error_messages={"max_length": "El comentario no puede pasar de 300 caracteres."},
        widget=forms.Textarea(attrs={
            "class": ATRS_TEXTO, "id": "comentario", "rows": 3, "maxlength": "300",
        }),
    )


class PagoSimuladoForm(forms.Form):
    """E2 / FN-17: pago SIMULADO (demo, sin pasarela real).

    Solo se pide el medio + últimos 4 dígitos si es tarjeta. NUNCA se pide
    ni se guarda el número completo ni el CVV: la referencia guardada en
    Pago.referencia_pasarela es un código simulado ("SIM-...").
    `resultado` es el botón de demo "simular éxito/fallo".
    """

    medio = forms.ChoiceField(
        label="Medio de pago",
        choices=[("", "Elige un medio")] + list(Pago.Medio.choices),
        error_messages={"invalid_choice": "Elige un medio de pago válido."},
        widget=forms.Select(attrs={"class": "form-select", "id": "medio"}),
    )
    ultimos4 = forms.CharField(
        label="Últimos 4 dígitos (solo si pagas con tarjeta)",
        max_length=4, min_length=4, required=False, strip=True,
        help_text="Solo los últimos 4, para la demo. Nunca escribas el número completo ni el CVV.",
        widget=forms.TextInput(attrs={
            "class": ATRS_TEXTO, "id": "ultimos4", "inputmode": "numeric",
            "maxlength": "4", "placeholder": "1234", "data-filtrar": "digitos",
        }),
    )
    resultado = forms.ChoiceField(
        choices=(("exito", "Simular pago exitoso"), ("fallo", "Simular pago fallido")),
        error_messages={"invalid_choice": "Resultado de simulación no válido."},
        widget=forms.HiddenInput(attrs={"id": "resultado"}),
    )
    motivo = forms.CharField(
        label="Motivo del fallo (solo si simulas un fallo)",
        max_length=255, required=False, strip=True,
        widget=forms.TextInput(attrs={
            "class": ATRS_TEXTO, "id": "motivo", "maxlength": "255",
            "placeholder": "Ej.: fondos insuficientes (demo)",
        }),
    )

    def clean_ultimos4(self):
        medio = (self.data.get("medio") or "").strip()
        ultimos4 = (self.cleaned_data.get("ultimos4") or "").strip()
        if medio == "tarjeta":
            if not re.fullmatch(r"\d{4}", ultimos4):
                raise ValidationError(
                    "Para tarjeta escribe solo los últimos 4 dígitos (4 números).")
        return ultimos4

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("resultado") == "fallo" and not (cleaned.get("motivo") or "").strip():
            cleaned["motivo"] = "Pago rechazado en la simulación (demo)."
        return cleaned


class DecisionTecnicoForm(forms.Form):
    """B3 / FN-14: decisión del admin sobre un técnico pendiente.

    - aprobar: sin motivo, pasa a activo con disponible=False.
    - rechazar: motivo OBLIGATORIO, pasa a rechazado.
    - info: pedir más información; sigue pendiente y la observación se guarda
      en motivo_rechazo sin cambiar el estado.
    """

    ACCIONES = (
        ("aprobar", "Aprobar"),
        ("rechazar", "Rechazar"),
        ("info", "Pedir información"),
        # Bloque G: corregir una aprobación (o rechazo) sin querer: vuelve a
        # pendiente_aprobacion con disponible=False, conservando todo.
        ("reabrir", "Reabrir revisión"),
    )

    tecnico_id = forms.IntegerField(widget=forms.HiddenInput)
    accion = forms.ChoiceField(choices=ACCIONES, widget=forms.HiddenInput)
    motivo = forms.CharField(
        label="Motivo / información solicitada", max_length=300, required=False,
        widget=forms.Textarea(attrs={
            "class": ATRS_TEXTO, "id": "motivo", "rows": 3, "maxlength": "300",
        }),
    )

    def clean(self):
        cleaned = super().clean()
        accion = cleaned.get("accion")
        motivo = (cleaned.get("motivo") or "").strip()
        if accion in ("rechazar", "info") and not motivo:
            self.add_error(
                "motivo",
                "El motivo es obligatorio para rechazar o pedir información.",
            )
        if accion not in ("aprobar", "rechazar", "info", "reabrir"):
            self.add_error("accion", "Acción no válida.")
        cleaned["motivo"] = motivo
        return cleaned


class SuspenderUsuarioForm(forms.Form):
    """B4 / FN-15: suspender (motivo OBLIGATORIO) o reactivar un usuario."""

    ACCIONES = (
        ("suspender", "Suspender"),
        ("reactivar", "Reactivar"),
    )

    usuario_id = forms.IntegerField(widget=forms.HiddenInput)
    accion = forms.ChoiceField(choices=ACCIONES, widget=forms.HiddenInput)
    motivo = forms.CharField(
        label="Motivo de la suspensión", max_length=300, required=False,
        widget=forms.Textarea(attrs={
            "class": ATRS_TEXTO, "id": "motivo", "rows": 3, "maxlength": "300",
        }),
    )

    def clean(self):
        cleaned = super().clean()
        accion = cleaned.get("accion")
        motivo = (cleaned.get("motivo") or "").strip()
        if accion == "suspender" and not motivo:
            self.add_error("motivo", "El motivo de la suspensión es obligatorio.")
        if accion not in ("suspender", "reactivar"):
            self.add_error("accion", "Acción no válida.")
        cleaned["motivo"] = motivo
        return cleaned


class DocumentoTecnicoForm(forms.ModelForm):
    """Bloque G: el técnico suma certificados extra (más conocimientos).

    El documento principal sigue siendo el de FN-8; estos son adicionales y
    se pueden borrar cuando se vuelven obsoletos.
    Bloque I: cada extra postula a una habilidad; el admin la aprueba y se
    suma a la especialidad principal para el matching.
    """

    class Meta:
        model = DocumentoTecnico
        fields = ["nombre", "especialidad", "archivo"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": ATRS_TEXTO, "id": "doc_nombre",
                "placeholder": "Ej. Diplomado en redes eléctricas",
            }),
            "especialidad": forms.Select(attrs={
                "class": "form-select", "id": "doc_especialidad",
            }),
            "archivo": forms.ClearableFileInput(attrs={
                "class": ATRS_TEXTO, "id": "doc_archivo", "accept": ".pdf,.jpg,.jpeg,.png",
            }),
        }


class DocumentoDecisionForm(forms.Form):
    """Bloque I: el admin aprueba o rechaza una habilidad postulada."""

    ACCIONES = (("aprobar_doc", "Aprobar"), ("rechazar_doc", "Rechazar"))

    documento_id = forms.IntegerField(widget=forms.HiddenInput)
    accion = forms.ChoiceField(choices=ACCIONES, widget=forms.HiddenInput)
    motivo = forms.CharField(max_length=300, required=False, strip=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("accion") == "rechazar_doc" and not (cleaned.get("motivo") or "").strip():
            self.add_error("motivo", "El motivo es obligatorio para rechazar.")
        if cleaned.get("accion") not in ("aprobar_doc", "rechazar_doc"):
            self.add_error("accion", "Acción no válida.")
        return cleaned


class PrecioEditarForm(forms.Form):
    """Bloque H: el dueño ajusta precio ofrecido/visibilidad en su pendiente."""

    precio_ofrecido = forms.DecimalField(
        label="Precio que ofreces (vacío = lo pone el técnico)",
        max_digits=10, decimal_places=0, min_value=1, required=False,
        error_messages={"min_value": "El precio ofrecido debe ser mayor que cero."},
        widget=forms.NumberInput(attrs={"class": ATRS_TEXTO, "id": "precio_ofrecido", "min": "1"}),
    )
    visible_tecnicos = forms.BooleanField(
        label="Visible para técnicos", required=False,
        widget=forms.CheckboxInput(attrs={"class": ATRS_CHECK, "id": "visible_tecnicos"}),
    )


class MontoDecisionForm(forms.Form):
    """Bloque H: el cliente acepta o rechaza el monto propuesto (anti-abuso)."""

    ACCIONES = (("aceptar_monto", "Aceptar"), ("rechazar_monto", "Rechazar"))

    solicitud_id = forms.IntegerField(widget=forms.HiddenInput)
    accion = forms.ChoiceField(choices=ACCIONES, widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("accion") not in ("aceptar_monto", "rechazar_monto"):
            self.add_error("accion", "Acción no válida.")
        return cleaned


class ResenaModerarForm(forms.Form):
    """Bloque G: el admin oculta o vuelve a mostrar una reseña.

    Bloque J: 'revisada' quita la etiqueta de revisión cuando el admin ya la
    vio y la considera válida (sin ocultarla).
    """

    ACCIONES = (("ocultar", "Ocultar"), ("mostrar", "Mostrar"),
                ("revisada", "Marcar revisada"))

    resena_id = forms.IntegerField(widget=forms.HiddenInput)
    accion = forms.ChoiceField(choices=ACCIONES, widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("accion") not in ("ocultar", "mostrar", "revisada"):
            self.add_error("accion", "Acción no válida.")
        return cleaned


class DesactivarCuentaForm(forms.Form):
    """Bloque G: baja voluntaria. Exige la contraseña actual como confirmación."""

    password = forms.CharField(
        label="Confirma con tu contraseña",
        widget=forms.PasswordInput(attrs={"class": ATRS_TEXTO, "id": "conf_clave"}),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_password(self):
        clave = self.cleaned_data.get("password") or ""
        if self.usuario is None or not self.usuario.check_password(clave):
            raise ValidationError("La contraseña no coincide.")
        return clave
