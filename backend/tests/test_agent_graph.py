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


def test_question_terms_absent_from_context_refuse_without_model():
    llm = FakeLLM()
    state, saved = run("¿Cuál es la capital de Colombia?", [chunk(0.9)], llm)
    assert state["refused"] is True and state["sources"] == []
    assert state["answer"].startswith(prompts.REFUSAL_MESSAGE)
    assert llm.calls == 0 and len(saved) == 1


def test_document_name_counts_as_context_for_the_lexical_check():
    llm = FakeLLM(["Briar es una campeona [1]."])
    lore = RetrievedChunk("Una joven sedienta de sangre.", 0.9, "doc-2", "Briar.md")
    state, _ = run("Hablame mas sobre Briar, su historia", [lore], llm)
    assert state["refused"] is False and llm.calls == 1


def test_grounded_answer_returns_sources():
    llm = FakeLLM(["Jinx es una criminal de Zaun [1]."])
    state, saved = run("¿Quién es Jinx?", [chunk(0.9), chunk(0.2, "ruido")], llm)
    assert state["refused"] is False
    assert state["answer"] == "Jinx es una criminal de Zaun [1]."
    assert [s["document"] for s in state["sources"]] == ["Jinx.md"]
    assert len(state["sources"]) == 1  # el chunk de 0.2 no llega al contexto
    assert len(saved) == 1


def test_model_no_info_is_converted_into_refusal():
    llm = FakeLLM(["NO_INFO"])
    state, _ = run("¿Quién es Jinx?", [chunk(0.9)], llm)
    assert state["refused"] is True
    assert state["answer"].startswith(prompts.REFUSAL_MESSAGE)
    assert state["sources"] == []


@pytest.mark.parametrize("text", [
    "Hola, ¿quién es Jinx?", "Hola ¿qué es Zaun?",
    "Gracias, ¿y Vi?", "Buenas, háblame de Ekko",
])
def test_greeting_plus_question_reaches_retrieval(text):
    llm = FakeLLM(["NO_INFO"])
    retrieved = []
    names = chunk(0.9, "Jinx, Zaun, Vi y Ekko son personajes de Piltóver.")
    graph = build_graph(lambda q, u: retrieved.append(q) or [names], llm, lambda s: None, 0.55)
    graph.invoke({"question": text, "user_id": "u1", "conversation_id": "c1"})
    assert retrieved == [text] and llm.calls == 1


@pytest.mark.parametrize("text", ["Hola", "Buenas tardes", "hey"])
def test_pure_greetings_stay_greetings(text):
    llm = FakeLLM()
    state, _ = run(text, [chunk(0.9)], llm)
    assert state["answer"] == prompts.GREETING_MESSAGE and llm.calls == 0


def test_no_info_anywhere_in_answer_is_refusal():
    llm = FakeLLM(["Lo siento, NO_INFO"])
    state, _ = run("¿Quién es Jinx?", [chunk(0.9)], llm)
    assert state["refused"] is True and state["sources"] == []
    assert state["answer"].startswith(prompts.REFUSAL_MESSAGE)


@pytest.mark.parametrize("text", ["Buenos días", "buenos días!", "Buenas tardes", "Gracias"])
def test_accented_greetings_are_detected(text):
    llm = FakeLLM()
    state, _ = run(text, [chunk(0.9)], llm)
    assert state["answer"] == prompts.GREETING_MESSAGE and llm.calls == 0
