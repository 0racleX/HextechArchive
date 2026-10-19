"""Verificación léxica determinista del contexto recuperado.

Reemplaza la llamada al modelo en `grade_context`: la pregunta solo se contesta si los términos
significativos que contiene (nombres propios, temas) aparecen en los fragmentos recuperados.
Es reproducible, no consume una pasada del modelo y deja a `generate` (NO_INFO) como segunda defensa.
"""
import difflib
import re
import unicodedata

MIN_MATCH_RATIO = 0.6

# Palabras funcionales, interrogativas y de petición.
_FUNCTION_WORDS = {
    "a", "al", "algo", "algun", "alguna", "alguno", "ante", "aqui", "como", "con", "contra", "cual", "cuales",
    "cuando", "cuanto", "cuantos", "cuanta", "cuantas", "de", "del", "desde", "donde", "dos", "el", "ella",
    "ellas", "ello", "ellos", "en", "entre", "era", "eres", "es", "esa", "ese", "eso", "esta", "estan", "este",
    "esto", "estoy", "fue", "ha", "hace", "hacen", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me",
    "mi", "mis", "muy", "no", "nos", "o", "otra", "otro", "para", "pero", "por", "porque", "pues", "que", "quien",
    "quienes", "se", "ser", "si", "sin", "sobre", "son", "su", "sus", "te", "tiene", "tienen", "tu", "tus", "un",
    "una", "uno", "unos", "unas", "y", "ya", "yo", "mejor", "peor", "puede", "pueden", "puedes", "dime", "dame",
    "hablame", "cuentame", "explicame", "explica", "cuenta", "habla", "quiero", "saber", "conocer", "decir",
    "mucho", "poco", "tambien", "cada", "todo", "todos", "toda", "todas", "algunos", "algunas", "del", "ver",
    "sabes", "dices", "puedo", "dar", "hacer",
    # verbos de petición ("¿qué puedes decirme de Jinx?")
    "decirme", "decirnos", "contarme", "contar", "mencionar", "menciona", "mencioname", "comentar", "comentame",
    "resumir", "resumeme", "explicar", "explicarme", "describe", "describir", "descripcion", "conoces",
    # peticiones abiertas ("dime un dato curioso", "sorpréndeme")
    "dato", "curioso", "curiosa", "curiosidad", "curiosidades", "interesante", "divertido", "divertida",
    "sorprendente", "azar", "aleatorio", "aleatoria", "random", "cualquier", "cualquiera", "sorprendeme",
    "sorprende", "recomiendame", "recomienda", "elige", "escoge", "quieras", "prefieras", "narra", "leyenda",
    "tienes",
    # saludos y cortesías
    "hola", "buenas", "buenos", "dias", "tardes", "noches", "gracias", "hey", "hi", "saludos", "favor", "porfa",
    "please", "disculpa", "perdon",
}

# Palabras presentes en casi todos los documentos del corpus: no distinguen un tema de otro.
_CORPUS_GENERIC = {
    "historia", "habilidad", "habilidades", "pasiva", "rol", "roles", "consejo", "consejos", "campeon",
    "campeones", "personaje", "region", "regiones", "reino", "informacion", "datos", "tema", "juego", "jugar",
    "enfrenta", "enfrentar", "enfrentarlo", "enfrentarla", "origen", "detalles", "mundo", "runeterra",
}

STOPWORDS = _FUNCTION_WORDS | _CORPUS_GENERIC
_TOKEN = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    plain = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    return plain.lower()


def stem(token: str) -> str:
    """Prefijo de 7 letras: empareja 'enfrenta'/'enfrentarlo' o 'relaciona'/'relacion' sin diccionario."""
    return token if len(token) < 7 else token[:7]


def significant_terms(question: str) -> list[str]:
    terms = []
    for tok in _TOKEN.findall(normalize(question)):
        if tok in STOPWORDS or (len(tok) < 2 and not tok.isdigit()):
            continue
        if stem(tok) not in terms:
            terms.append(stem(tok))
    return terms


def _significant_tokens(question: str) -> list[str]:
    out = []
    for tok in _TOKEN.findall(normalize(question)):
        if tok in STOPWORDS or (len(tok) < 2 and not tok.isdigit()):
            continue
        if tok not in out:
            out.append(tok)
    return out


def _osa_distance(a: str, b: str) -> int:
    """Distancia de edición con transposiciones adyacentes (Damerau, variante OSA)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


EXACT, PARTIAL, FUZZY = 3, 2, 1


def term_match_level(q: str, n: str) -> int:
    """Cómo coincide el término de la pregunta `q` con el término de un nombre `n`.

    EXACT (mismo prefijo), PARTIAL ('kaiser' dentro de 'mordekaiser') o FUZZY (error de escritura:
    'jinks' ~ 'jinx'); 0 si no coinciden. Parcial y aproximado exigen al menos 4 letras.
    """
    if q == n or stem(q) == stem(n):
        return EXACT
    if min(len(q), len(n)) < 4:
        return 0
    if q in n or n in q:
        return PARTIAL
    allowed = 1 if max(len(q), len(n)) <= 4 else 2
    if q[0] == n[0] and abs(len(q) - len(n)) <= 2 and _osa_distance(q, n) <= allowed:
        return FUZZY
    return 0


def context_matches(question: str, context_text: str, min_ratio: float = MIN_MATCH_RATIO, names=()) -> bool:
    """True si al menos `min_ratio` de los términos significativos de la pregunta aparece en el contexto.

    `names` son los nombres de los documentos recuperados: permiten reconocer nombres parciales o con
    errores de escritura ('Kaiser' -> 'Mordekaiser.md').
    """
    terms = _significant_tokens(question)
    if not terms:
        return False
    context_stems = {stem(tok) for tok in _TOKEN.findall(normalize(context_text))}
    name_tokens = [tok for nm in names for tok in _TOKEN.findall(normalize(nm)) if tok not in _NAME_NOISE]
    matched = 0
    for term in terms:
        if stem(term) in context_stems or any(term_match_level(term, nt) for nt in name_tokens):
            matched += 1
    return matched / len(terms) >= min_ratio


_NAME_NOISE = {"md", "txt", "pdf", "csv", "docx", "json", "region"}


def document_match_level(document_name: str, question: str) -> int:
    """Nivel (EXACT/PARTIAL/FUZZY) con el que TODOS los términos del nombre aparecen en la pregunta; 0 si no."""
    name_terms = [
        tok for tok in _TOKEN.findall(normalize(document_name))
        if tok not in _NAME_NOISE and tok not in STOPWORDS and len(tok) >= 2
    ]
    if not name_terms:
        return 0
    question_tokens = _significant_tokens(question)
    level = EXACT
    for nt in name_terms:
        best = max((term_match_level(q, nt) for q in question_tokens), default=0)
        if best == 0:
            return 0
        level = min(level, best)
    return level


def document_matches_question(document_name: str, question: str) -> bool:
    """True si el nombre del documento aparece en la pregunta (exacto, parcial o con errores de escritura).

    'Briar.md' <- 'cuéntame la historia de Briar'; 'Mordekaiser.md' <- 'la historia de Kaiser'.
    """
    return document_match_level(document_name, question) > 0


# --- Peticiones de ayuda sobre el propio agente ("¿qué puedes hacer?", "¿qué información me puedes responder?") ---
_HELP_PATTERNS = [
    re.compile(r"\bque (puedo|puedes|podria|podrias|sabes|haces|eres|ofreces)\b"),
    re.compile(r"\bque (informacion|temas|cosas|datos)\b.*\b(puedo|puedes|podria|tienes|manejas|sabes|respondes|responder|consultar)\b"),
    re.compile(r"\ben que (me )?(puedes|podrias) ayudar\b"),
    re.compile(r"\bde que (puedes )?(hablar|saber)\b"),
    re.compile(r"\bcomo (funcionas|te uso|se usa)\b"),
    re.compile(r"\bquien eres\b"),
    re.compile(r"\bayuda\b"),
]
# Palabras que solo hablan del propio agente: si la pregunta contiene otro término, no es una petición de ayuda.
_HELP_WORDS = {
    "puedo", "puedes", "podria", "podrias", "podes", "sabes", "haces", "hacer", "eres", "ofreces", "tienes",
    "manejas", "respondes", "responder", "consultar", "preguntar", "ayudar", "ayuda", "funcionas", "hablar",
    "informacion", "temas", "cosas", "datos", "acerca", "contigo", "conmigo", "lol", "league", "legends",
    "comandos", "usar", "uso", "saber", "quien", "funcionar", "sirves", "sirve",
}


def is_help_request(question: str) -> bool:
    """True si el usuario pregunta qué puede hacer/consultar con el agente (y no por un personaje o tema)."""
    plain = normalize(question)
    if not any(p.search(plain) for p in _HELP_PATTERNS):
        return False
    leftover = [t for t in _TOKEN.findall(plain) if t not in STOPWORDS and t not in _HELP_WORDS and len(t) >= 2]
    return not leftover


# --- Saludos por parecido: "holi", "holiwi", "olaa", "buen día", "wenas" ---------------------------------------
_GREETING_VOCAB = {
    "hola", "holi", "ola", "buenas", "buenos", "buen", "dias", "dia", "tardes", "noches", "saludos", "hello",
    "hey", "ey", "hi", "wenas", "buenaas", "que", "tal", "todos", "todas", "amigo", "amigos", "archivista",
}
_NOT_GREETINGS = {"olaf"}  # nombres de campeón parecidos a un saludo


def is_greeting(text: str) -> bool:
    """True si el mensaje entero (máx. 3 palabras, sin pregunta) está formado por palabras de saludo,
    permitiendo alargamientos y errores de escritura ('holaaa', 'holiwi')."""
    if "?" in text or "¿" in text:
        return False
    words = _TOKEN.findall(normalize(text))
    if not words or len(words) > 3:
        return False
    return all(
        w not in _NOT_GREETINGS
        and (w in _GREETING_VOCAB or difflib.get_close_matches(w, _GREETING_VOCAB, n=1, cutoff=0.78))
        for w in words
    )


# --- Charla breve: cortesías y comentarios sociales sin contenido sobre LoL -------------------------------------
_SMALLTALK_PATTERNS = [
    re.compile(p) for p in (
        r"\bcomo (estas|andas|te va|vas|has estado|te encuentras)\b",
        r"\bque tal\b",
        r"\bque onda\b",
        r"\btodo bien\b",
        r"(^|\b)(muchas )?gracias\b",
        r"\b(adios|chao|chau|hasta luego|hasta pronto|nos vemos|bye)\b",
        r"^(ja|je|ji|jo|jaja|jeje)+\b",
        r"^(ok|okay|vale|listo|genial|perfecto|bien|bueno|claro|dale|excelente|entiendo|entendido)\b",
        r"\b(bonito|lindo|hermoso|buen|buenisimo) dia\b",
        r"\bque (lindo|bonito|buen|hermoso) dia\b",
    )
]
_SMALLTALK_WORDS = {
    "como", "estas", "andas", "te", "va", "vas", "has", "estado", "encuentras", "que", "tal", "onda", "todo", "bien",
    "muchas", "gracias", "adios", "chao", "chau", "hasta", "luego", "pronto", "nos", "vemos", "bye", "ok", "okay",
    "vale", "listo", "genial", "perfecto", "bueno", "claro", "dale", "excelente", "entiendo", "entendido", "bonito",
    "lindo", "hermoso", "buen", "buenisimo", "dia", "por", "todo", "y", "tu",
}
_LAUGH = re.compile(r"^(ja|je|ji|jo)+$")


def is_smalltalk(text: str) -> bool:
    """True si es una cortesía/comentario social corto y no menciona ningún personaje ni tema."""
    plain = normalize(text)
    words = _TOKEN.findall(plain)
    if not words or len(words) > 7 or not any(p.search(plain) for p in _SMALLTALK_PATTERNS):
        return False
    leftover = [
        w for w in words
        if w not in STOPWORDS and w not in _SMALLTALK_WORDS and not _LAUGH.match(w) and len(w) >= 2
    ]
    return not leftover


# --- Peticiones sobre el catálogo: listas, conteos y "cuéntame algo al azar" -------------------------------------
_RANDOM_TRIGGER = re.compile(
    r"\b(algun|alguna|algunos|cualquier|cualquiera|al azar|aleatori\w+|random|sorprend\w+|recomiend\w+|elige|escoge|"
    r"quieras|prefieras|dato curioso|curiosidad\w*|algo curioso|algo interesante|algo divertido)\b"
)
_RANDOM_SUBJECT = re.compile(
    r"\b(campeon\w*|personaje\w*|region\w*|historia\w*|lore|dato\w*|curios\w+|interesante|leyenda\w*|cuent\w+|narr\w+)\b"
)
_LIST_ASK = re.compile(r"\b(nombres?|lista|listado|cuales|que|dime|dame|muestra\w*|enumera\w*)\b")


def detect_catalog_request(question: str) -> dict | None:
    """Detecta peticiones que se resuelven con el catálogo de documentos, sin buscar contexto.

    Devuelve {"kind": "list"|"count"|"random_story"|"random_fact", "subject": "champion"|"region", "letter": str|None}
    o None si la pregunta es normal (incluida cualquiera que nombre un personaje concreto).
    """
    plain = normalize(question)
    subject = "region" if re.search(r"\bregion\w*", plain) and not re.search(r"\bcampeon\w*", plain) else "champion"

    # 1) aleatorias: solo si NO nombran un personaje o tema concreto
    if _RANDOM_TRIGGER.search(plain) and _RANDOM_SUBJECT.search(plain):
        leftover = [t for t in _TOKEN.findall(plain) if t not in STOPWORDS and len(t) >= 2]
        if not leftover:
            kind = "random_fact" if re.search(r"\b(dato\w*|curios\w+|interesante|divertid\w+)\b", plain) else "random_story"
            return {"kind": kind, "subject": subject, "letter": None}

    # 2) conteos
    if re.search(r"\bcuant[oa]s\b", plain) and re.search(r"\b(campeon\w*|regiones?)\b", plain):
        return {"kind": "count", "subject": subject, "letter": None}

    # 3) listas de campeones por letra
    m = re.search(r"\bcampeon\w*\b.*\b(?:por|con)\b (?:la letra )?([a-z])\b", plain)
    if m and (_LIST_ASK.search(plain) or re.search(r"\bcampeon\w*\b", plain)):
        return {"kind": "list", "subject": "champion", "letter": m.group(1)}

    # 4) listas sin letra
    if re.search(r"\b(lista|listado|nombres?|cuales)\b.*\bcampeon\w*|\bque campeon\w* (hay|tienes|conoces|manejas)\b", plain):
        return {"kind": "list", "subject": "champion", "letter": None}
    if _LIST_ASK.search(plain) and re.search(r"\bregion(es)?\b", plain) and not re.search(r"\b(es|son|significa)\b", plain):
        return {"kind": "list", "subject": "region", "letter": None}
    return None
