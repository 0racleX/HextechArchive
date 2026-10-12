import re
import unicodedata
from types import SimpleNamespace

from langgraph.config import get_stream_writer

from app.agents import prompts

GREETING = re.compile(r"^\s*(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|hi|gracias)\b", re.I)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().strip().upper()


def _format_context(chunks) -> str:
    return "\n\n".join(f"[{i}] ({c.document_name}) {c.content}" for i, c in enumerate(chunks, 1))


def make_nodes(retriever, llm, save_history, threshold: float) -> SimpleNamespace:
    def validate_intent(state):
        q = state["question"].strip()
        if len(q) < 3 or not re.search(r"\w{2}", q):
            return {"intent": "invalid"}
        m = GREETING.match(q)
        if m:
            rest = re.sub(r"[^\w\s]", " ", q[m.end():])
            if "?" not in q and "¿" not in q and len(rest.split()) <= 2:
                return {"intent": "greeting"}
        return {"intent": "ok"}

    def retrieve(state):
        return {"chunks": retriever(state["question"], state["user_id"])}

    def grade_context(state):
        good = [c for c in state["chunks"] if c.score >= threshold]
        if not good:
            return {"chunks": [], "context_ok": False}
        verdict = llm.invoke(
            prompts.GRADE_PROMPT.format(context=_format_context(good), question=state["question"])
        ).content
        ok = re.match(r"^\W*SI\b", _norm(verdict)) is not None
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
            return {"answer": f"{prompts.REFUSAL_MESSAGE} {prompts.SUGGESTION}", "sources": [], "refused": True}
        sources = [
            {"document": c.document_name, "snippet": c.content[:240], "score": round(c.score, 3)}
            for c in state["chunks"]
        ]
        return {"answer": answer, "sources": sources, "refused": False}

    def refuse(state):
        intent = state.get("intent")
        if intent == "greeting":
            return {"answer": prompts.GREETING_MESSAGE, "sources": [], "refused": False}
        if intent == "invalid":
            return {"answer": prompts.INVALID_MESSAGE, "sources": [], "refused": True}
        return {"answer": f"{prompts.REFUSAL_MESSAGE} {prompts.SUGGESTION}", "sources": [], "refused": True}

    def save(state):
        save_history(state)
        return {}

    return SimpleNamespace(
        validate_intent=validate_intent, retrieve=retrieve, grade_context=grade_context,
        generate=generate, refuse=refuse, save=save,
    )
