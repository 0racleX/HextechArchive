"""Verificación léxica determinista del contexto recuperado.

Reemplaza la llamada al modelo en `grade_context`: la pregunta solo se contesta si los términos
significativos que contiene (nombres propios, temas) aparecen en los fragmentos recuperados.
Es reproducible, no consume una pasada del modelo y deja a `generate` (NO_INFO) como segunda defensa.
"""
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


def context_matches(question: str, context_text: str, min_ratio: float = MIN_MATCH_RATIO) -> bool:
    """True si al menos `min_ratio` de los términos significativos de la pregunta aparece en el contexto."""
    terms = significant_terms(question)
    if not terms:
        return False
    context_stems = {stem(tok) for tok in _TOKEN.findall(normalize(context_text))}
    matched = sum(1 for t in terms if t in context_stems)
    return matched / len(terms) >= min_ratio


_NAME_NOISE = {"md", "txt", "pdf", "csv", "docx", "json", "region"}


def document_matches_question(document_name: str, question: str) -> bool:
    """True si TODOS los términos significativos del nombre del documento aparecen en la pregunta.

    'Briar.md' <- 'cuéntame la historia de Briar'; 'Region-Islas de la Sombra.md' exige 'islas' y 'sombra'.
    """
    name_terms = [
        stem(tok) for tok in _TOKEN.findall(normalize(document_name))
        if tok not in _NAME_NOISE and tok not in STOPWORDS and len(tok) >= 2
    ]
    if not name_terms:
        return False
    question_terms = set(significant_terms(question))
    return all(t in question_terms for t in name_terms)


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
