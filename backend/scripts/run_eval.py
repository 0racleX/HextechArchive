"""Mide cuántas preguntas se responden/rechazan correctamente. Uso: python -m scripts.run_eval [umbral]

Nota: la última pregunta del set ("¿Quién es Briar?") solo debe rechazarse mientras
Briar.md NO esté cargado en el corpus; si lo está, elimínala de questions.json (o
cámbiala a "answer") antes de calibrar.

Los imports pesados (app.deps, agentes) son perezosos: importar este módulo no toca BD ni red.
"""
import json
import sys
import uuid
from pathlib import Path

QUESTIONS = Path(__file__).resolve().parents[1] / "tests" / "eval" / "questions.json"


def score(got: list[str], expected: list[str]) -> tuple[int, int]:
    hits = sum(g == e for g, e in zip(got, expected))
    return hits, len(expected)


def format_row(expect: str, got: str, top_sim: float, question: str) -> str:
    mark = "OK " if got == expect else "FAIL"
    return f"{mark} esperado={expect:<6} obtenido={got:<6} top_sim={top_sim:.2f}  {question}"


def main() -> None:
    from app.agents.graph import build_graph
    from app.agents.llm import build_llm
    from app.config import get_settings
    from app.deps import get_embedder, get_vector_store

    settings = get_settings()
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else settings.similarity_threshold
    store, embedder = get_vector_store(), get_embedder()
    user = str(uuid.uuid4())  # usuario sin documentos propios: solo ve el corpus compartido

    def retriever(question, user_id):
        return store.search(embedder.embed_query(question), user_id, settings.top_k)

    graph = build_graph(retriever, build_llm(settings), lambda s: None, threshold)
    rows = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    got_all: list[str] = []
    for item in rows:
        state = graph.invoke({"question": item["q"], "user_id": user, "conversation_id": "eval"})
        got = "refuse" if state["refused"] else "answer"
        got_all.append(got)
        top = max((c.score for c in state.get("chunks", [])), default=0.0)
        print(format_row(item["expect"], got, top, item["q"]))
    ok, total = score(got_all, [r["expect"] for r in rows])
    print(f"\numbral={threshold}  aciertos={ok}/{total}  ({ok / total:.0%})")


if __name__ == "__main__":
    main()
