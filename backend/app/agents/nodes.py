import random
import re
import unicodedata
from types import SimpleNamespace

from langgraph.config import get_stream_writer

from app.agents import prompts
from app.agents.lexical import (
    context_matches,
    detect_catalog_request,
    is_greeting,
    is_help_request,
    is_smalltalk,
)

SOCIAL_MAX_WORDS = 8     # solo los mensajes cortos pueden ser charla; los largos son preguntas
SOCIAL_MAX_CHARS = 300
MAX_LISTED = 40


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def _norm(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().strip().upper()


def _format_context(chunks) -> str:
    return "\n\n".join(f"[{i}] ({c.document_name}) {c.content}" for i, c in enumerate(chunks, 1))


def _title(document_name: str) -> str:
    return re.sub(r"\.[A-Za-z0-9]{1,5}$", "", document_name).removeprefix("Region-").strip()


def _split_catalog(names) -> tuple[list[str], list[str]]:
    """Nombres de documentos -> (campeones y otros documentos, regiones), sin duplicados y ordenados."""
    regions = sorted({_title(n) for n in names if n.startswith("Region-")}, key=str.casefold)
    champions = sorted({_title(n) for n in names if not n.startswith("Region-")}, key=str.casefold)
    return champions, regions


def _refusal() -> dict:
    return {"answer": f"{prompts.REFUSAL_MESSAGE} {prompts.SUGGESTION}", "sources": [], "refused": True}


def make_nodes(retriever, llm, save_history, threshold: float, catalog=None, rng=None) -> SimpleNamespace:
    """`catalog(user_id) -> list[str]` devuelve los nombres de los documentos visibles y listos; sin él se
    desactivan las listas y las peticiones aleatorias."""
    rng = rng or random.Random()

    def validate_intent(state):
        q = state["question"].strip()
        if is_greeting(q):  # primero los saludos: "hi" o "ey" miden menos de 3 caracteres pero son válidos
            return {"intent": "greeting"}
        if len(q) < 3 or not re.search(r"\w{2}", q):
            return {"intent": "invalid"}
        if is_help_request(q):
            return {"intent": "help"}
        if is_smalltalk(q):
            return {"intent": "smalltalk"}
        if catalog is not None:
            request = detect_catalog_request(q)
            if request:
                return {"intent": "catalog", "catalog": request}
        return {"intent": "ok"}

    def pick_topic(state):
        """Petición abierta ("cuéntame algo de algún campeón"): elige un tema al azar del catálogo y reformula."""
        champions, regions = _split_catalog(catalog(state["user_id"]))
        pool = regions if state["catalog"]["subject"] == "region" else champions
        if not pool:
            return {"intent": "ok"}  # sin catálogo disponible: sigue el flujo normal con la pregunta original
        title = rng.choice(pool)
        if state["catalog"]["kind"] == "random_fact":
            question = f"Dime un dato curioso sobre {title}."
        else:
            question = f"Cuéntame la historia de {title}."
        return {"original_question": state["question"], "question": question}

    def catalog_answer(state):
        request = state["catalog"]
        champions, regions = _split_catalog(catalog(state["user_id"]))
        if request["kind"] == "count":
            text = f"Tengo {len(champions)} campeones y {len(regions)} regiones en mi base de conocimiento."
        elif request["subject"] == "region":
            text = f"Regiones en mi base de conocimiento ({len(regions)}): " + ", ".join(regions) + "."
        elif request["letter"]:
            letter = request["letter"]
            hits = [c for c in champions if _strip_accents(c)[:1].lower() == letter]
            if hits:
                shown = ", ".join(hits[:MAX_LISTED])
                text = f"Campeones que empiezan por {letter.upper()} ({len(hits)}): {shown}."
            else:
                text = f"No encuentro campeones que empiecen por {letter.upper()} en mi base de conocimiento."
        else:
            text = (f"Tengo {len(champions)} campeones. Dime con qué letra empieza el nombre y te los listo "
                    "(por ejemplo: «campeones por K»).")
        return {"answer": text, "sources": [], "refused": False}

    def retrieve(state):
        return {"chunks": retriever(state["question"], state["user_id"])}

    def grade_context(state):
        # Verificación determinista (sin llamada al modelo): umbral de similitud + los términos
        # significativos de la pregunta deben aparecer en el contexto o en el nombre de los documentos
        # recuperados (admite nombres parciales o con errores). `generate` conserva NO_INFO como segunda defensa.
        good = [c for c in state["chunks"] if c.score >= threshold]
        text = " ".join(f"{c.document_name} {c.content}" for c in good)
        ok = bool(good) and context_matches(state["question"], text, names=[c.document_name for c in good])
        return {"chunks": good if ok else [], "context_ok": ok}

    def generate(state):
        writer = get_stream_writer()
        prompt = prompts.GENERATE_PROMPT.format(
            context=_format_context(state["chunks"]), question=state["question"]
        )
        parts = []
        for piece in llm.stream(prompt):
            parts.append(piece.content)
            writer({"token": piece.content})
        answer = "".join(parts).strip()
        if not answer or "NO_INFO" in _norm(answer):
            return _refusal()
        sources = [
            {"document": c.document_name, "snippet": c.content[:240], "score": round(c.score, 3)}
            for c in state["chunks"]
        ]
        return {"answer": answer, "sources": sources, "refused": False}

    def social(state):
        """Sin contexto útil: si el mensaje es charla informal responde en tono social (sin datos); si no, rechaza."""
        text = state.get("original_question") or state["question"]
        if len(re.findall(r"\w+", text)) > SOCIAL_MAX_WORDS:
            return _refusal()
        verdict = llm.invoke(prompts.SOCIAL_CLASSIFY_PROMPT.format(question=text)).content
        if not _norm(verdict).startswith("CHARLA"):
            return _refusal()
        reply = llm.invoke(prompts.SOCIAL_REPLY_PROMPT.format(question=text)).content.strip()
        if not reply:
            return _refusal()
        return {"answer": reply[:SOCIAL_MAX_CHARS], "sources": [], "refused": False}

    def refuse(state):
        intent = state.get("intent")
        if intent == "greeting":
            return {"answer": prompts.GREETING_MESSAGE, "sources": [], "refused": False}
        if intent == "help":
            return {"answer": prompts.HELP_MESSAGE, "sources": [], "refused": False}
        if intent == "smalltalk":
            return {"answer": prompts.SMALLTALK_MESSAGE, "sources": [], "refused": False}
        if intent == "invalid":
            return {"answer": prompts.INVALID_MESSAGE, "sources": [], "refused": True}
        return _refusal()

    def save(state):
        save_history(state)
        return {}

    return SimpleNamespace(
        validate_intent=validate_intent, pick_topic=pick_topic, catalog_answer=catalog_answer, retrieve=retrieve,
        grade_context=grade_context, generate=generate, social=social, refuse=refuse, save=save,
    )
