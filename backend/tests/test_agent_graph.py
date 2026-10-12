from types import SimpleNamespace

import pytest

from app.agents import prompts
from app.agents.graph import build_graph
from app.repositories.models import RetrievedChunk


class FakeLLM:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls = 0

    def _next(self):
        self.calls += 1
        return self.responses.pop(0)

    def invoke(self, prompt):
        return SimpleNamespace(content=self._next())

    def stream(self, prompt):
        for word in self._next().split(" "):
            yield SimpleNamespace(content=word + " ")


def chunk(score, text="Jinx es una criminal de Zaun."):
    return RetrievedChunk(text, score, "doc-1", "Jinx.md")


def run(question, chunks, llm, threshold=0.55):
    saved = []
    graph = build_graph(lambda q, u: chunks, llm, saved.append, threshold)
    state = graph.invoke({"question": question, "user_id": "u1", "conversation_id": "c1"})
    return state, saved


def test_greeting_does_not_touch_the_model():
    llm = FakeLLM()
    state, saved = run("Hola", [chunk(0.9)], llm)
    assert state["answer"] == prompts.GREETING_MESSAGE
    assert state["refused"] is False
    assert llm.calls == 0 and len(saved) == 1


@pytest.mark.parametrize("text", ["", "  ", "a", "??"])
def test_too_short_question_is_rejected_without_model(text):
    llm = FakeLLM()
    state, saved = run(text, [chunk(0.9)], llm)
    assert state["refused"] is True
    assert state["answer"] == prompts.INVALID_MESSAGE
    assert llm.calls == 0 and len(saved) == 1


def test_no_chunks_refuses_with_literal_message():
    llm = FakeLLM()
    state, saved = run("¿Cómo se prepara el sushi?", [], llm)
    assert state["refused"] is True
    assert state["answer"].startswith(prompts.REFUSAL_MESSAGE)
    assert llm.calls == 0 and len(saved) == 1


def test_low_similarity_chunks_are_discarded():
    llm = FakeLLM()
    state, _ = run("¿Quién es Jinx?", [chunk(0.30), chunk(0.40)], llm)
    assert state["refused"] is True and llm.calls == 0


def test_grader_says_no_refuses():
    llm = FakeLLM(["NO"])
    state, _ = run("¿Quién es Jinx?", [chunk(0.9)], llm)
    assert state["refused"] is True
    assert llm.calls == 1
    assert state["sources"] == []


def test_grounded_answer_returns_sources():
    llm = FakeLLM(["SÍ", "Jinx es una criminal de Zaun [1]."])
    state, saved = run("¿Quién es Jinx?", [chunk(0.9), chunk(0.2, "ruido")], llm)
    assert state["refused"] is False
    assert state["answer"] == "Jinx es una criminal de Zaun [1]."
    assert [s["document"] for s in state["sources"]] == ["Jinx.md"]
    assert len(state["sources"]) == 1  # el chunk de 0.2 no llega al contexto
    assert len(saved) == 1


def test_model_no_info_is_converted_into_refusal():
    llm = FakeLLM(["SI", "NO_INFO"])
    state, _ = run("¿Quién es Jinx?", [chunk(0.9)], llm)
    assert state["refused"] is True
    assert state["answer"].startswith(prompts.REFUSAL_MESSAGE)
    assert state["sources"] == []
