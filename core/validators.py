"""Validadores compartidos por los modelos de core."""
import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# FN-1 / FN-8: cédula solo números, de 6 a 10 dígitos.
validar_cedula = RegexValidator(
    regex=r"^\d{6,10}$",
    message="La cédula debe tener solo números, entre 6 y 10 dígitos.",
)

# FN-1 / FN-2 / FN-8 / FN-9: nombre 3–100, solo letras, espacios, tildes y ñ.
validar_nombre = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{3,100}$",
    message="El nombre debe tener entre 3 y 100 caracteres (solo letras).",
)

def validar_telefono(valor):
    """FN-1/FN-2/FN-8/FN-9: entre 7 y 15 dígitos.

    Se aceptan +, espacios y guiones como separadores, pero NO letras ni
    otros símbolos (casos de prueba CP-FN1-10, CP-FN2-08, CP-FN8-09 y
    CP-FN9-09 exigen el rechazo de letras).
    """
    valor = (valor or "").strip()
    if not re.fullmatch(r"\+?[0-9][0-9\s\-]*", valor):
        raise ValidationError(
            "El teléfono solo puede tener números (se permiten +, espacios "
            "y guiones, pero no letras).")
    digitos = re.sub(r"\D", "", valor)
    if not 7 <= len(digitos) <= 15:
        raise ValidationError(
            "Ingresa un teléfono válido (entre 7 y 15 dígitos).")


EXTENSIONES_CERTIFICACION = ("pdf", "jpg", "jpeg", "png")
EXTENSIONES_FOTO = ("jpg", "jpeg", "png")
TAMANO_MAX_MB = 5


def _validar_archivo(archivo, extensiones):
    ext = archivo.name.rsplit(".", 1)[-1].lower()
    if ext not in extensiones:
        raise ValidationError(f"Formato no permitido. Debe ser: {', '.join(extensiones)}.")
    if archivo.size > TAMANO_MAX_MB * 1024 * 1024:
        raise ValidationError(f"El archivo no puede pesar más de {TAMANO_MAX_MB} MB.")


def validar_certificacion(archivo):
    """FN-8: documento de certificación, PDF o imagen, máx. 5MB."""
    _validar_archivo(archivo, EXTENSIONES_CERTIFICACION)


def validar_foto(archivo):
    """FN-3 / FN-12: fotos jpg/png, máx. 5MB."""
    _validar_archivo(archivo, EXTENSIONES_FOTO)
