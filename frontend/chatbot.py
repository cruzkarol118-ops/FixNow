"""Asistente orientador de FixNow.

El widget ayuda a una persona a elegir el tipo de servicio o a entender
cómo funciona FixNow. No diagnostica, no cotiza, no crea solicitudes y no
accede a datos privados. Reutiliza el clasificador existente de forma
silenciosa: si no hay confianza suficiente, no sugiere nada.
"""

import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.ia import predecir_categoria

# Límites defensivos: el endpoint es público.
_TEXTO_MAX = 300
_RESPUESTAS_PRODUCTO = {
    "como funciona": "FixNow conecta a un cliente con un técnico verificado cercano. El cliente describe el daño, compara calificación, distancia y precio de referencia, y paga cuando el trabajo termina.",
    "verificacion": "Cada técnico se registra con sus datos, cédula y certificación. Un administrador revisa la información y aprueba o rechaza la cuenta antes de que pueda recibir solicitudes.",
    "precio": "Antes de elegir, ves el precio de referencia del técnico. El monto final se acuerda y se confirma al finalizar el servicio.",
    "pago": "El pago se realiza cuando el trabajo está listo y confirmado.",
    "mapa": "Puedes ver los técnicos disponibles en lista o en mapa, con distancia y calificación.",
    "cuenta": "Puedes crear cuenta de cliente o registrarte como técnico. El técnico queda pendiente de aprobación hasta que un administrador lo verifique.",
}
_TEMA_POR_CLAVE = {
    "como funciona": "como funciona",
    "como funciona fixnow": "como funciona",
    "que es fixnow": "como funciona",
    "verificacion": "verificacion",
    "verificado": "verificacion",
    "tecnico verificado": "verificacion",
    "precio": "precio",
    "precio referencia": "precio",
    "cuanto cobra": "precio",
    "pago": "pago",
    "pagar": "pago",
    "mapa": "mapa",
    "lista": "mapa",
    "cuenta": "cuenta",
    "registrarme": "cuenta",
    "registro": "cuenta",
}


_RIESGO = ("gas", "humo", "fuego", "chispa", "inund", "explosion", "quemad")

# Palabras clave claras por categoría. Solo se usan como respaldo cuando el
# clasificador se abstiene (no hay suficiente confianza). No son diagnóstico:
# el usuario siempre puede elegir otra categoría.
_PALABRAS_CATEGORIA = {
    "plomeria": ("tuberia", "tubería", "fuga", "goteo", "gotea", "griferia",
                 "grifería", "lavaplatos", "lavamanos", "inodoro", "sanitario",
                 "desague", "desagüe", "caneria", "cañeria", "canalizacion",
                 "destapar", "regadera", "ducha", "sanitario", "humedad"),
    "electricidad": ("tomacorriente", "enchufe", "interruptor", "breaker",
                     "luz", "bombillo", "cable", "cableado", "chispa",
                     "cortocircuito", "tablero", "voltaje", "corriente"),
    "cerrajeria": ("llave", "chapa", "cerradura", "puerta", "candado",
                   "guarda", "picaporte", "cilindro", "porton", "portón"),
    "electrodomesticos": ("nevera", "lavadora", "microondas", "televisor",
                          "estufa", "secadora", "licuadora", "aspiradora",
                          "aire acondicionado", "congelador", "horno"),
}


def _categoria_por_palabras(texto):
    t = (texto or "").lower()
    coincidencias = []
    for cat, palabras in _PALABRAS_CATEGORIA.items():
        if any(p in t for p in palabras):
            coincidencias.append(cat)
    # Solo sugerir si una sola categoría coincide (evitar ambigüedad).
    if len(coincidencias) == 1:
        return coincidencias[0]
    return None


def _es_riesgo(texto):
    t = (texto or "").lower()
    return any(r in t for r in _RIESGO)


def _normalizar(texto):
    return " ".join((texto or "").strip().lower().split())


def _respuesta_producto(pregunta):
    """Devuelve (clave, texto) si la pregunta coincide con un tema conocido."""
    p = _normalizar(pregunta)
    if not p:
        return None
    for clave, tema in _TEMA_POR_CLAVE.items():
        if clave in p:
            return tema, _RESPUESTAS_PRODUCTO[tema]
    return None


@require_POST
def chatbot_orientar(request):
    """Endpoint público, sin persistencia. Devuelve orientación de categoría
    o respuesta de producto. Nunca crea/consulta solicitudes ni devuelve PII."""
    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "json_invalido"}, status=400)

    texto = (data.get("texto") or "")[:_TEXTO_MAX]
    texto = texto.strip()

    # 0) Riesgo: priorizar seguridad, pero sin bloquear la orientación.
    # El aviso se muestra igual; si se puede sugerir una categoría (clasificador
    # o palabras clave), se ofrece también para que la persona pueda pedir
    # ayuda sin quedarse sin salida.
    es_riesgo = _es_riesgo(texto)
    if es_riesgo:
        # Solo se intenta sugerir categoría cuando el riesgo es eléctrico
        # (chispas): la persona necesita un electricista. Otros riesgos
        # (gas, fuego, inundación, explosión) son emergencias puras.
        solo_chispa = "chispa" in (texto or "").lower()
        categoria_r = None
        confianza_r = 0.0
        if solo_chispa:
            categoria_r = _categoria_por_palabras(texto)
            confianza_r = 0.5 if categoria_r else 0.0
            if categoria_r is None and len(texto.split()) >= 3:
                try:
                    from core.ia import predecir_categoria as _pc
                    c, conf = _pc(texto)
                    if c is not None:
                        categoria_r, confianza_r = c, float(conf or 0.0)
                except Exception:
                    pass
        from core.models import Categoria as _Cat
        nombre_r = dict(_Cat.choices).get(categoria_r) if categoria_r else None
        return JsonResponse({
            "ok": True,
            "tipo": "riesgo",
            "tema": None,
            "respuesta": (
                "Si hay riesgo de gas, fuego, inundación o descarga eléctrica, "
                "aléjate del peligro y llama a los servicios de emergencia. "
                "FixNow no diagnostica ni da instrucciones de reparación."
            ),
            "categoria": categoria_r,
            "nombre": nombre_r,
            "confianza": round(float(confianza_r or 0.0), 2),
        })

    # 1) Tema de producto (FAQ)
    prod = _respuesta_producto(texto)
    if prod is not None:
        tema, respuesta = prod
        return JsonResponse({
            "ok": True,
            "tipo": "producto",
            "tema": tema,
            "respuesta": respuesta,
            "categoria": None,
            "nombre": None,
            "confianza": 0.0,
        })

    # Detectar si el texto menciona términos de más de una categoría: en ese
    # caso no se sugiere nada (evitar orientación contradictoria).
    _cats_mencionadas = [c for c, ps in _PALABRAS_CATEGORIA.items()
                         if any(p in (texto or "").lower() for p in ps)]

    # 2) Orientación de categoría (reutiliza clasificador; respaldo por palabras)
    if len(texto.split()) >= 3 and len(_cats_mencionadas) <= 1:
        categoria, confianza = predecir_categoria(texto)
    else:
        categoria, confianza = None, 0.0

    if categoria is None and len(_cats_mencionadas) <= 1:
        # Respaldo: si el texto menciona términos claros de una sola categoría,
        # se sugiere como orientación (no como diagnóstico).
        categoria = _categoria_por_palabras(texto)
        confianza = 0.0 if categoria is None else 0.5
    if len(_cats_mencionadas) >= 2:
        categoria = None
        confianza = 0.0

    from core.models import Categoria
    nombre = None
    if categoria:
        nombre = dict(Categoria.choices).get(categoria)

    respuesta = None
    if categoria:
        respuesta = (
            f"Por lo que describes, parece un problema de {nombre}. "
            "Puedes usar esa categoría o elegir otra; tú decides."
        )
    else:
        respuesta = (
            "No tengo suficiente información para sugerir una categoría. "
            "Describe con un poco más de detalle qué se dañó y dónde, "
            "o elige la categoría que mejor encaje."
        )

    return JsonResponse({
        "ok": True,
        "tipo": "categoria",
        "tema": None,
        "respuesta": respuesta,
        "categoria": categoria,
        "nombre": nombre,
        "confianza": round(float(confianza or 0.0), 2),
    })
