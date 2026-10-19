"""Mide cuántas preguntas se responden/rechazan correctamente. Uso: python -m scripts.run_eval [umbral]

Nota: la última pregunta del set ("¿Quién es Briar?") solo debe rechazarse mientras
Briar.md NO esté cargado en el corpus; si lo está, elimínala de questions.json (o
cámbiala a "answer") antes de calibrar.

El set incluye paráfrasis, preguntas en inglés, erratas y trampas fuera de dominio que comparten un nombre
de campeón ("Dame la receta de Darius"). Las respuestas esperadas solo usan datos del corpus compartido
(Data Dragon + regiones): los documentos de demo_docs/lore se suben a mano en la demo y no los ve el usuario
anónimo de esta evaluación. Las preguntas en inglés además dependen de que la similitud entre embeddings
inglés/español supere el umbral; si fallan con top_sim bajo, el problema es la recuperación, no el grader.
El grader léxico se prueba sin BD ni Ollama en tests/test_lexical.py.

top_sim es el score CRUDO más alto devuelto por el retriever (antes del filtro de
umbral); "n/a" si la recuperación no llegó a ejecutarse.

Los imports pesados (app.deps, agentes) son perezosos: importar este módulo no toca BD ni red.
"""
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

QUESTIONS = Path(__file__).resolve().parents[1] / "tests" / "eval" / "questions.json"
MIN_HIT_RATE = 0.85
ERROR = "ERROR"


def score(got: list[str], expected: list[str]) -> tuple[int, int]:
    assert len(got) == len(expected), "got y expected deben tener la misma longitud"
    hits = sum(g == e for g, e in zip(got, expected))
    return hits, len(expected)


def format_row(expect: str, got: str, top_sim: Optional[float], question: str, detail: str = "") -> str:
    mark = "OK " if got == expect else "FAIL"
    top = "n/a" if top_sim is None else f"{top_sim:.2f}"
    extra = f"  [{detail}]" if detail else ""
    return f"{mark} esperado={expect:<6} obtenido={got:<6} top_sim={top}  {question}{extra}"


def should_fail(got: list[str], expected: list[str]) -> list[str]:
    """Razones por las que la evaluación falla (lista vacía = éxito)."""
    reasons = []
    hits, total = score(got, expected)
    if any(g == "answer" and e == "refuse" for g, e in zip(got, expected)):
        reasons.append("se respondió una pregunta que debía rechazarse")
    if any(g == ERROR for g in got):
        reasons.append("hubo errores de ejecución")
    if total and hits / total < MIN_HIT_RATE:
        reasons.append(f"aciertos {hits / total:.0%} < {MIN_HIT_RATE:.0%}")
    return reasons


def main() -> None:
    from app.agents.graph import build_graph
    from app.agents.llm import build_llm
    from app.agents.retrieval import build_retriever
    from app.config import get_settings
    from app.deps import get_embedder, get_vector_store

    settings = get_settings()
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else settings.similarity_threshold
    store, embedder = get_vector_store(), get_embedder()
    user = str(uuid.uuid4())  # usuario sin documentos propios: solo ve el corpus compartido
    raw_top: list[Optional[float]] = [None]

    base_retriever = build_retriever(store, embedder, settings.top_k)

    def retriever(question, user_id):
        chunks = base_retriever(question, user_id)
        raw_top[0] = max((c.score for c in chunks), default=0.0)
        return chunks

    graph = build_graph(retriever, build_llm(settings), lambda s: None, threshold)
    rows = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    got_all: list[str] = []
    for item in rows:
        raw_top[0] = None
        detail = ""
        try:
            state = graph.invoke({"question": item["q"], "user_id": user, "conversation_id": "eval"})
            got = "refuse" if state["refused"] else "answer"
        except Exception as exc:  # noqa: BLE001 - un fallo no debe abortar la evaluación
            got = ERROR
            detail = f"{type(exc).__name__}: {exc}"
        got_all.append(got)
        print(format_row(item["expect"], got, raw_top[0], item["q"], detail))
    expected = [r["expect"] for r in rows]
    ok, total = score(got_all, expected)
    errors = got_all.count(ERROR)
    print(f"\numbral={threshold}  aciertos={ok}/{total}  ({ok / total:.0%})  errors={errors}")
    reasons = should_fail(got_all, expected)
    if reasons:
        print("FALLO: " + "; ".join(reasons))
        sys.exit(1)


if __name__ == "__main__":
    main()
