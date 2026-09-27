"""Bloque F — IA académica de FixNow (F1 clasificador, F2 sentimiento).

F1: Naive Bayes + TF-IDF con bigramas, entrenado con ~100 frases de ejemplo
en español (redacciones reales, typos y textos cortos). Devuelve
(categoria, confianza); bajo el umbral no sugiere nada (mejor silencio que
una sugerencia mala). Si scikit-learn no está instalado, todo devuelve
fallback silencioso y el formulario sigue funcionando.

F2: análisis de sentimiento por léxico en español, SIN dependencias:
listas de palabras positivas, negativas y agresivas + manejo de negaciones
("no fue malo" no cuenta como negativo). Devuelve (polaridad, alerta_bool).
"""

import hashlib
import re
import unicodedata

# Stemming español (confla repararlo=reparar, bombillo=bombilla...).
# Snowball es algorítmico: no descarga datos. Si nltk falta, se sigue sin
# stemming (la IA nunca rompe por una dependencia).
try:
    from nltk.stem.snowball import SnowballStemmer
    _STEM = SnowballStemmer("spanish")
except Exception:
    _STEM = None

# ---------------------------------------------------------------------
# F1. Clasificador de categoría
# ---------------------------------------------------------------------

# Con pocos datos las probabilidades NB salen planas y un umbral absoluto
# mata la cobertura; el margen top1-top2 discrimina mejor lo seguro de lo
# dudoso (medido en evaluar_ia).
MARGEN_CONFIANZA = 0.10
# "otro" es el cajón fallback: sugerirlo casi no ahorra nada al usuario, así
# que exige evidencia fuerte; las categorías informativas sugieren con 0.10.
MARGEN_OTRO = 0.25

# ~100 frases (20 por categoría): vocabulario típico de cada oficio,
# redacciones coloquiales, typos comunes y textos cortos como los que
# escribe un cliente apurado.
EJEMPLOS = [
    # plomeria
    ("Hay una fuga de agua debajo del lavaplatos y gotea todo el dia", "plomeria"),
    ("Goteo constante bajo el lavamanos del bano", "plomeria"),
    ("El inodoro no deja de botar agua y el tanque no llena", "plomeria"),
    ("Se revento la tuberia de la cocina y se inunda todo", "plomeria"),
    ("La griferia de la ducha gotea y pierde presion", "plomeria"),
    ("Se tapo el sifon del lavamanos y no baja el agua", "plomeria"),
    ("El sanitario suena toda la noche y no corta el agua", "plomeria"),
    ("Hay humedad en la pared del bano, creo que hay fuga interna", "plomeria"),
    ("La llave del lavadero no cierra bien y chorrea", "plomeria"),
    ("Se dano la ducha electrica, sale fria y con poquita agua", "plomeria"),
    ("El desague de la cocina se devuelve cuando lavo los platos", "plomeria"),
    ("Necesito destapar la caneria del patio que esta tapada", "plomeria"),
    ("El flotador del tanque se quedo pegado", "plomeria"),
    ("Gotea la conexion del lavaplatos por debajo", "plomeria"),
    ("Se partio el tubo del agua caliente", "plomeria"),
    ("El bano se inundo porque no traga el sifon", "plomeria"),
    ("Quiero cambiar la griferia vieja del bano", "plomeria"),
    ("Sale muy poquita agua en la regadera", "plomeria"),
    ("Hay mal olor que sale del desague", "plomeria"),
    ("Se tapo el bano", "plomeria"),
    # electricidad
    ("El tomacorriente de la sala hace chispa al conectar", "electricidad"),
    ("Se fue la luz en la cocina y el breaker se dispara", "electricidad"),
    ("El interruptor del cuarto no prende el bombillo", "electricidad"),
    ("Hay un cortocircuito en el tablero electrico", "electricidad"),
    ("El ventilador de techo no enciende, creo que es el cableado", "electricidad"),
    ("La toma de la alcoba echa chispas y huele a quemado", "electricidad"),
    ("Se baja la luz cada vez que prendo el microondas", "electricidad"),
    ("No hay luz en toda la casa desde anoche", "electricidad"),
    ("El taco de la ducha se calienta mucho", "electricidad"),
    ("Parpadean los bombillos del pasillo sin razon", "electricidad"),
    ("Necesito instalar un punto electrico para la nevera", "electricidad"),
    ("El cable del timbre esta pelado y da corrientazos", "electricidad"),
    ("Se quemo el enchufe donde conecto la plancha", "electricidad"),
    ("El medidor de luz hace un ruido raro", "electricidad"),
    ("No funciona el interruptor doble de la sala", "electricidad"),
    ("Huele a quemado cerca de la caja de tacos", "electricidad"),
    ("Quiero poner lamparas nuevas en el techo", "electricidad"),
    ("El voltaje esta muy bajo y no arranca la bomba", "electricidad"),
    ("Hace corto cuando conecto dos cosas a la vez", "electricidad"),
    ("Se apaga todo si prendo la ducha electrica", "electricidad"),
    # cerrajeria
    ("Perdi las llaves y no puedo abrir la puerta principal", "cerrajeria"),
    ("La chapa de la puerta se trabo y no gira la llave", "cerrajeria"),
    ("Necesito cambiar las guardas de la cerradura", "cerrajeria"),
    ("La puerta quedo bloqueada con el seguro puesto", "cerrajeria"),
    ("El candado del garaje no abre, la llave se partio dentro", "cerrajeria"),
    ("Me quede por fuera y deje las llaves adentro", "cerrajeria"),
    ("La cerradura del cuarto no asegura bien", "cerrajeria"),
    ("Necesito duplicado de la llave del apartamento", "cerrajeria"),
    ("La puerta de metal no cierra, el picaporte no engancha", "cerrajeria"),
    ("Se dano el cilindro de la chapa principal", "cerrajeria"),
    ("Quiero una chapa de seguridad para la entrada", "cerrajeria"),
    ("El porton electrico no abre con el control", "cerrajeria"),
    ("La llave gira en falso y no abre nada", "cerrajeria"),
    ("Se quedo la llave pegada en la cerradura", "cerrajeria"),
    ("Necesito abrir una caja fuerte vieja sin clave", "cerrajeria"),
    ("La reja de la ventana no asegura", "cerrajeria"),
    ("Cambiar la guarda porque me robaron el bolso con llaves", "cerrajeria"),
    ("No abre la puerta del local", "cerrajeria"),
    # electrodomesticos
    ("La lavadora no centrifuga y hace mucho ruido", "electrodomesticos"),
    ("El televisor no enciende, solo parpadea el led", "electrodomesticos"),
    ("La nevera no enfria en la parte de abajo", "electrodomesticos"),
    ("El horno microondas no calienta la comida", "electrodomesticos"),
    ("La licuadora se quemo y huele a quemado al conectarla", "electrodomesticos"),
    ("La estufa no prende un quemador", "electrodomesticos"),
    ("El aire acondicionado bota agua adentro", "electrodomesticos"),
    ("La secadora da vueltas pero no seca la ropa", "electrodomesticos"),
    ("La nevera hace un ruido fuerte cada rato", "electrodomesticos"),
    ("El televisor se ve borroso y con rayas", "electrodomesticos"),
    ("La lavadora bota agua por debajo", "electrodomesticos"),
    ("El congelador hace mucho hielo en las paredes", "electrodomesticos"),
    ("La olla arrocera no calienta", "electrodomesticos"),
    ("La aspiradora perdio succion", "electrodomesticos"),
    ("El microondas prende pero el plato no gira", "electrodomesticos"),
    ("La estufa huele a gas cuando la prendo", "electrodomesticos"),
    ("El ventilador solo funciona en una velocidad", "electrodomesticos"),
    ("La nevera no congela nada", "electrodomesticos"),
    ("Se dano la tarjeta del televisor", "electrodomesticos"),
    ("La lavadora se mueve mucho al centrifugar", "electrodomesticos"),
    ("Se me dano el computador y no prende", "electrodomesticos"),
    ("El portatil esta muy lento y se calienta", "electrodomesticos"),
    ("Mi cafetera no calienta el agua", "electrodomesticos"),
    ("La cafetera gotea por debajo", "electrodomesticos"),
    ("No me funciona la cafetera", "electrodomesticos"),
    ("Se estropeo el computador y no prende", "electrodomesticos"),
    ("El televisor se estropeo con el apagon", "electrodomesticos"),
    ("Se me estropeo la lavadora", "electrodomesticos"),
    # otro
    ("Necesito pintar la sala y resanar las paredes", "otro"),
    ("Quiero instalar una repisa y colgar un espejo en la sala", "otro"),
    ("Se dano la bisagra de la puerta del closet de madera", "otro"),
    ("Necesito armar un mueble nuevo que compre desarmado", "otro"),
    ("Hay que impermeabilizar la terraza antes del invierno", "otro"),
    ("Quiero poner cortinas nuevas en toda la casa", "otro"),
    ("El techo tiene una gotera cuando llueve duro", "otro"),
    ("Necesito podar el jardin y arreglar el prado", "otro"),
    ("Se callo un pedazo de panete de la pared", "otro"),
    ("Quiero enchapar el bano con ceramica nueva", "otro"),
    ("Hay que resanar las grietas de la fachada", "otro"),
    ("Necesito un aseo profundo despues de la remodelacion", "otro"),
    ("Instalar un mueble de bano flotante", "otro"),
    ("La puerta del closet se salio del riel", "otro"),
    ("Pintar el apartamento completo antes de arrendarlo", "otro"),
    ("Arreglar el piso laminado que se levanto", "otro"),
    ("Poner papel tapiz en la pared de la sala", "otro"),
    ("Necesito ayuda para trastearme este fin de semana", "otro"),
    ("Cortar el cesped y fumigar las matas", "otro"),
    ("La llave de la puerta principal no gira, es la cerradura", "cerrajeria"),
    ("Necesito copia de la llave de la entrada del edificio", "cerrajeria"),
    ("La llave del agua del lavadero quedo abierta", "plomeria"),
    ("Cierra la llave de paso del agua para el arreglo", "plomeria"),
    ("La bomba de agua no arranca por problema electrico", "electricidad"),
    ("El portero electrico no suena cuando timbran", "electricidad"),
    ("La puerta de madera del closet necesita bisagra nueva", "otro"),
    ("El riel del closet se salio y la puerta no corre", "otro"),
    ("La nevera dejo de enfriar de un momento a otro", "electrodomesticos"),
    ("El motor de la nevera suena raro al arrancar", "electrodomesticos"),
    ("Quiero una cerradura nueva con llaves de seguridad", "cerrajeria"),
    ("La chapa electrica del porton no abre", "cerrajeria"),
    ("Se estalló la regadera de la ducha y sale el chorro para todo lado", "plomeria"),
    ("La regadera no bota agua", "plomeria"),
    ("Se dano un bombillo de la sala y no prende", "electricidad"),
    ("Se fundio el bombillo del bano", "electricidad"),
    ("Se dano el microondas, no calienta nada", "electrodomesticos"),
    ("El microondas no prende ni calienta", "electrodomesticos"),
    ("Se dano el microondas de la cocina", "electrodomesticos"),
    ("Se fundieron los bombillos de la casa", "electricidad"),
    ("No prenden los bombillos del apartamento", "electricidad"),
    ("Se fundio la bombilla de la sala", "electricidad"),
    ("Cambiar la bombilla del bano que no prende", "electricidad"),
    ("Poner un foco nuevo en el patio", "electricidad"),
    # Criterio verbo (aparato vs trabajo): instalar/cablear/punto es trabajo
    # eléctrico; no gira/no prende/reparar es el aparato (electrodoméstico).
    ("Instalar un ventilador de techo nuevo en la alcoba", "electricidad"),
    ("Poner un punto electrico para el ventilador de la sala", "electricidad"),
    ("Cablear la ducha electrica que hace corto", "electricidad"),
    ("Instalar lamparas de techo en el comedor", "electricidad"),
    ("El ventilador no gira aunque si prende", "electrodomesticos"),
    ("Reparar el ventilador que hace ruido al girar", "electrodomesticos"),
    ("La ducha electrica no calienta el agua", "electrodomesticos"),
    ("Cambiar la resistencia de la ducha electrica", "electrodomesticos"),
]

_MODELO = None
_IA_NO_DISPONIBLE = False
# Cuántas muestras había cuando se entrenó el caché: si llegan nuevas por el
# uso, el próximo predecir reentrena solo (el `reentrenar_ia` por consola corre
# en OTRO proceso y no limpiaría este caché).
_MODELO_N_MUESTRAS = None


def _n_muestras():
    try:
        from core.models import IASugerencia
        return IASugerencia.objects.exclude(
            categoria_final__isnull=True).count()
    except Exception:
        return 0


def _normalizar(texto):
    """Minúsculas sin tildes para que 'chispa' y 'chispá' coincidan."""
    texto = (texto or "").lower()
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("ascii")


def huella(texto):
    """(sha256, normalizado) para guardar muestras sin el texto original."""
    norm = _normalizar(texto)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest(), norm


def _muestras_extra():
    """Bloque D: frases que el sistema aprendió del uso (IASugerencia).

    Import perezoso para no crear dependencia circular con core.models.
    """
    try:
        from core.models import IASugerencia
    except Exception:
        return []
    try:
        return [
            (m.texto_muestra, m.categoria_final)
            for m in IASugerencia.objects.filter(
                categoria_final__isnull=False)
        ]
    except Exception:
        return []


def _entrenar():
    """Entrena (una sola vez) y cachea el pipeline TF-IDF + Naive Bayes.

    Incluye las muestras aprendidas del uso (Bloque D). Devuelve
    (vectorizador, clasificador) o None si scikit-learn no está instalado
    o algo falla: el llamador debe tratar None como "sin IA".
    """
    global _MODELO, _IA_NO_DISPONIBLE, _MODELO_N_MUESTRAS
    n = _n_muestras()
    if _MODELO is not None and _MODELO_N_MUESTRAS == n:
        return _MODELO
    if _IA_NO_DISPONIBLE:
        return None
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB
    except ImportError:
        _IA_NO_DISPONIBLE = True
        return None
    try:
        base = list(EJEMPLOS)
        extra = _muestras_extra()
        datos = base + extra
        textos = [_normalizar(t) for t, _ in datos]
        etiquetas = [c for _, c in datos]
        # Lo aprendido del uso pesa x5: una corrección real vale más que mis
        # frases sintéticas, si no una sola muestra nunca movería al modelo.
        pesos = [1] * len(base) + [5] * len(extra)
        vectorizador = TfidfVectorizer(
            tokenizer=_tokens_stem, preprocessor=None,
            lowercase=False, token_pattern=None)
        matriz = vectorizador.fit_transform(textos)
        # fit_prior=False: con pocas frases por clase, los priors por conteo
        # le dan ventaja injusta a la categoría con más ejemplos (medido:
        # electricidad se comía a las demás). Priors uniformes.
        clasificador = MultinomialNB(fit_prior=False)
        clasificador.fit(matriz, etiquetas, sample_weight=pesos)
        _MODELO = (vectorizador, clasificador)
        _MODELO_N_MUESTRAS = n
    except Exception:
        _IA_NO_DISPONIBLE = True
        return None
    return _MODELO


def reiniciar_modelo():
    """Olvida el modelo cacheado para reentrenar (tras aprender muestras)."""
    global _MODELO, _IA_NO_DISPONIBLE, _MODELO_N_MUESTRAS
    _MODELO = None
    _IA_NO_DISPONIBLE = False
    _MODELO_N_MUESTRAS = None


def predecir_categoria(texto, margen=MARGEN_CONFIANZA):
    """F1: (categoria|None, confianza:float) para un texto libre.

    1) Piso mínimo: menos de 3 palabras con letras → silencio directo
    (una palabra suelta es moneda al aire, no sugerencia).
    2) Naive Bayes: si el margen top1-top2 alcanza, sugiere.
    3) Si duda, segunda oportunidad por similitud difusa (rapidfuzz,
    token_set): cubre typos y redacciones cercanas sin entrenar de más.
    Si nada convence: (None, margen), mejor silencio que sugerencia mala.
    Sin texto o sin dependencias: (None, 0.0). Nunca lanza excepción.
    """
    if len(_tokens(texto or "")) < 3:
        return (None, 0.0)
    modelo = _entrenar()
    if modelo is None:
        return (None, 0.0)
    vectorizador, clasificador = modelo
    try:
        probas = clasificador.predict_proba(
            vectorizador.transform([_normalizar(texto)]))[0]
        orden = sorted(probas, reverse=True)
        ventaja = float(orden[0] - orden[1]) if len(orden) > 1 else float(orden[0])
        categoria = str(clasificador.classes_[int(probas.argmax())])
        minimo = MARGEN_OTRO if categoria == "otro" else margen
        if ventaja >= minimo:
            return (categoria, ventaja)
    except Exception:
        return (None, 0.0)
    return _parecido_difuso(texto)


_FUZZY_MIN = 70  # medido: typos ~74, peticiones genéricas ~50s.
_FUZZY_CACHE = None


def _parecido_difuso(texto):
    """Fallback: la frase de entrenamiento más parecida (token_set_ratio).

    Solo si el parecido >= 70 (medido: typos ~74, peticiones genéricas ~50s):
    typos ("microhondas") y redacciones cercanas sin necesidad de entrenar
    cada variante a mano. Textos de menos de 12 caracteres ni se intentan
    (monosílabos = moneda). Sin rapidfuzz: silencio.
    """
    global _FUZZY_CACHE
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return (None, 0.0)
    try:
        norm = _normalizar(texto)
        if len(norm) < 12:
            return (None, 0.0)
        if _FUZZY_CACHE is None:
            _FUZZY_CACHE = (
                [_normalizar(t) for t, _ in EJEMPLOS],
                [c for _, c in EJEMPLOS],
            )
        base_norm, base_cat = _FUZZY_CACHE
        hallado = process.extractOne(
            norm, base_norm, scorer=fuzz.token_set_ratio)
        if hallado:
            cat = base_cat[hallado[2]]
            minimo = 90 if cat == "otro" else _FUZZY_MIN
            if hallado[1] >= minimo:
                return (cat, round(hallado[1] / 100, 2))
        return (None, 0.0)
    except Exception:
        return (None, 0.0)


# ---------------------------------------------------------------------
# F2. Sentimiento por léxico (sin dependencias)
# ---------------------------------------------------------------------

POSITIVAS = frozenset("""
bueno buena buen bien buenos buenas excelente genial perfecto perfecta perfectos
amable amables puntual puntuales rapido rapida rapidos cordial atento atenta
recomendado recomendada recomiendo profesional profesionales limpio limpia
impecable cumplido cumplidor cumplio honesto honesta barato justo justa
gracias satisfecho satisfecha feliz contento contenta maravilloso increible
eficiente responsables responsable cuidadoso esmerado cumplida ayudo ayuda
soluciono arreglo impecables economico cumplida cumplidas servicial
serviciales educado educada respetuoso barato rapidisimo buenisimo
encantado encantada fascinado contentisimo
""".split())

NEGATIVAS = frozenset("""
malo mala malos malas pesimo pesima pesimos terrible terribles horrible
horribles lento lenta tarde tardes impuntual impuntuales grosero grosera
sucio sucia caros caro cara estafa robo dano danos rompio roto rota
peor peores decepcion decepciono arrepentido arrepentida nunca jamas problema
problemas falla fallo fallas defectuoso incompleto incumplido incumplio
irresponsable deshonesto mentiroso mentira flojo descuidado descuido
demora demorado incumplidor informal cobro costoso feo cochino lentitud
malisimo malisima desastroso desastre pesimo lentisimo carisimo demoradisimo
impuntualisimo atrevido conchudo descarado sinverguenza
""".split())

AGRESIVAS = frozenset("""
idiota imbecil estupido pendejo malparido hijueputa gonorrea pirobo marrano
bruto bruta inutil ladron ladrones rata ratas tramposo tramposa hp hpta
maldito maldita desgraciado desgraciada porqueria basura asco odio amenazas
amenaza amenazo mataria estafa estafador ratero atracador inmundo asqueroso
miserable porquerias mierda carajo jodido jodida malditos tonto tonta torpe
incompetente mediocre ladrona ratera triplehijueputa carechimba sapo
""".split())

# Bloque E: palabras que invierten lo que sigue ("no fue malo" no es negativo).
NEGACIONES = frozenset(["no", "nunca", "jamas", "tampoco", "sin", "ni"])


def _tokens(texto):
    """Tokens en crudo (sentimiento y piso mínimo: el léxico no va stemmeado)."""
    return re.findall(r"[a-z]+", _normalizar(texto))


def _tokens_stem(texto):
    """Tokens con stemming para el vectorizador (repararlo=reparar...)."""
    toks = _tokens(texto)
    if _STEM is None:
        return toks
    try:
        return [_STEM.stem(t) for t in toks]
    except Exception:
        return toks


def analizar_sentimiento(texto, estrellas=None):
    """F2: (polaridad:int, alerta:bool) para el comentario de una calificación.

    polaridad = #positivas − #negativas (las agresivas restan 2).
    Las negaciones invierten la palabra siguiente en una ventana de 3
    ("no fue malo" suma en vez de restar). Hay alerta cuando hay 2+ insultos,
    cuando un insulto viene SIN nada positivo que lo matice ("eres un idiota"
    sí alerta; "jodida fuga... pero quedó muy bien" no), cuando un 5★ viene
    con texto negativo (incongruencia) o cuando el texto es muy negativo
    (polaridad <= −4).
    """
    toks = _tokens(texto or "")
    pos, neg, agresivas = 0, 0, 0
    for i, tok in enumerate(toks):
        if tok in AGRESIVAS:
            agresivas += 1
            continue
        # ¿Hay negación en las 3 palabras anteriores?
        negado = any(t in NEGACIONES for t in toks[max(0, i - 3):i])
        if tok in POSITIVAS:
            if negado:
                neg += 1
            else:
                pos += 1
        elif tok in NEGATIVAS:
            if negado:
                pos += 1
            else:
                neg += 1
    polaridad = pos - neg - 2 * agresivas
    alerta = False
    if agresivas >= 2:
        alerta = True
    elif agresivas == 1 and pos == 0:
        alerta = True
    elif estrellas == 5 and polaridad < 0:
        alerta = True
    elif polaridad <= -4:
        alerta = True
    return (polaridad, alerta)
