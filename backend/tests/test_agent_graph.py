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
    llm = FakeLLM(["OTRO"])  # sin contexto, una sola llamada breve: la clasificación social
    state, saved = run("¿Cómo se prepara el sushi?", [], llm)
    assert state["refused"] is True
    assert state["answer"].startswith(prompts.REFUSAL_MESSAGE)
    assert llm.calls == 1 and len(saved) == 1


def test_low_similarity_chunks_are_discarded():
    llm = FakeLLM(["OTRO"])
    state, _ = run("¿Quién es Jinx?", [chunk(0.30), chunk(0.40)], llm)
    assert state["refused"] is True and llm.calls == 1  # nunca llegó a generate


def test_question_terms_absent_from_context_refuse_without_generating():
    llm = FakeLLM(["OTRO"])
    state, saved = run("¿Cuál es la capital de Colombia?", [chunk(0.9)], llm)
    assert state["refused"] is True and state["sources"] == []
    assert state["answer"].startswith(prompts.REFUSAL_MESSAGE)
    assert llm.calls == 1 and len(saved) == 1


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


@pytest.mark.parametrize("text", ["Buenos días", "buenos días!", "Buenas tardes"])
def test_accented_greetings_are_detected(text):
    llm = FakeLLM()
    state, _ = run(text, [chunk(0.9)], llm)
    assert state["answer"] == prompts.GREETING_MESSAGE and llm.calls == 0


@pytest.mark.parametrize("text", [
    "Holi", "Oli", "Ola", "Holaaa", "Hello", "Buen día", "buen dia", "Buenas", "Saludos", "Ey",
])
def test_more_greeting_variants_are_detected(text):
    llm = FakeLLM()
    state, saved = run(text, [chunk(0.9)], llm)
    assert state["answer"] == prompts.GREETING_MESSAGE and state["refused"] is False
    assert llm.calls == 0 and len(saved) == 1


@pytest.mark.parametrize("text", [
    "¿Qué puedo consultar acerca de lol contigo?", "Que informacion me puedes responder?",
    "¿Qué puedes hacer?", "ayuda", "Hola, ¿qué puedes hacer?",
])
def test_help_requests_get_the_help_message_without_touching_the_model(text):
    llm = FakeLLM()
    state, saved = run(text, [chunk(0.9)], llm)
    assert state["answer"] == prompts.HELP_MESSAGE
    assert state["refused"] is False and state["sources"] == []
    assert llm.calls == 0 and len(saved) == 1


def test_question_about_a_character_is_not_hijacked_by_help():
    llm = FakeLLM(["Jinx es una criminal de Zaun [1]."])
    state, _ = run("¿Qué puedes decirme de Jinx?", [chunk(0.9)], llm)
    assert state["refused"] is False and llm.calls == 1


# ---------------------------------------------------------------------------------------------------------------
# Conversación general: charla, catálogo, peticiones aleatorias y respaldo social
# ---------------------------------------------------------------------------------------------------------------
import random  # noqa: E402

CATALOG = ["Zed.md", "Jinx.md", "Kaisa.md", "Kalista.md", "Region-Zaun.md", "Region-Demacia.md"]


def run_conv(question, llm, chunks=(), catalog=CATALOG, seed=1):
    saved, retrieved = [], []

    def retriever(q, u):
        retrieved.append(q)
        return list(chunks)

    graph = build_graph(retriever, llm, saved.append, 0.55,
                        catalog=(lambda uid: list(catalog)) if catalog is not None else None, rng=random.Random(seed))
    state = graph.invoke({"question": question, "user_id": "u1", "conversation_id": "c1"})
    return state, saved, retrieved


@pytest.mark.parametrize("text", ["Holiwi", "Olaa", "Holaaa", "Buen día", "wenas"])
def test_fuzzy_greetings_reach_the_greeting_reply(text):
    llm = FakeLLM()
    state, saved, _ = run_conv(text, llm)
    assert state["answer"] == prompts.GREETING_MESSAGE and llm.calls == 0 and len(saved) == 1


@pytest.mark.parametrize("text", ["¿Cómo estás?", "Bonito dia", "Gracias", "jajaja"])
def test_smalltalk_gets_a_friendly_reply_without_the_model(text):
    llm = FakeLLM()
    state, _, _ = run_conv(text, llm)
    assert state["answer"] == prompts.SMALLTALK_MESSAGE and state["refused"] is False and llm.calls == 0


def test_random_story_picks_a_champion_and_answers_from_its_context():
    llm = FakeLLM(["Zed lidera la Orden de la Sombra [1]."])
    ctx = [chunk(0.9, "Zed Jinx Kaisa Kalista: historias de campeones.")]
    state, saved, retrieved = run_conv("Cuéntame la historia de algún campeón", llm, ctx, seed=3)
    assert retrieved[0].startswith("Cuéntame la historia de ")
    title = retrieved[0].removeprefix("Cuéntame la historia de ").rstrip(".")
    assert title in {"Zed", "Jinx", "Kaisa", "Kalista"}          # nunca una región
    assert state["refused"] is False
    assert saved[0]["original_question"] == "Cuéntame la historia de algún campeón"


def test_random_region_only_picks_regions():
    for seed in range(8):
        _, _, retrieved = run_conv("Háblame de alguna región", FakeLLM(["Texto."] * 1), [chunk(0.9, "Zaun Demacia")], seed=seed)
        assert retrieved[0].removeprefix("Cuéntame la historia de ").rstrip(".") in {"Zaun", "Demacia"}


def test_random_fact_uses_a_fact_request():
    _, _, retrieved = run_conv("Dime un dato curioso", FakeLLM(["Dato."]), [chunk(0.9, "Zed Jinx Kaisa Kalista")], seed=2)
    assert retrieved[0].startswith("Dime un dato curioso sobre ")


def test_random_request_with_empty_catalog_does_not_crash():
    llm = FakeLLM(["OTRO"])
    state, _, _ = run_conv("Cuéntame la historia de algún campeón", llm, [], catalog=[])
    assert state["refused"] is True


def test_list_champions_by_letter_comes_from_the_catalog():
    llm = FakeLLM()
    state, saved, retrieved = run_conv("Nombres de campeones por K", llm)
    assert "Kaisa" in state["answer"] and "Kalista" in state["answer"] and "Zed" not in state["answer"]
    assert "Zaun" not in state["answer"] and state["refused"] is False
    assert llm.calls == 0 and retrieved == [] and len(saved) == 1


def test_list_letter_without_matches_says_so():
    state, _, _ = run_conv("campeones por Q", FakeLLM())
    assert "Q" in state["answer"] and state["refused"] is False


def test_count_and_region_list():
    state, _, _ = run_conv("¿Cuántos campeones hay?", FakeLLM())
    assert "4" in state["answer"] and "2" in state["answer"]
    state, _, _ = run_conv("¿Qué regiones hay?", FakeLLM())
    assert "Zaun" in state["answer"] and "Demacia" in state["answer"] and "Jinx" not in state["answer"]


def test_catalog_is_ignored_when_not_configured():
    llm = FakeLLM(["OTRO"])
    state, _, _ = run_conv("Nombres de campeones por K", llm, [], catalog=None)
    assert state["refused"] is True


def test_social_fallback_answers_chitchat_without_facts():
    llm = FakeLLM(["CHARLA", "¡Qué bueno! ¿Quieres saber de algún campeón?"])
    state, _, _ = run_conv("Me siento feliz hoy", llm, [])
    assert state["answer"].startswith("¡Qué bueno!") and state["refused"] is False and llm.calls == 2
    assert state["sources"] == []


def test_social_fallback_still_refuses_real_questions():
    llm = FakeLLM(["OTRO"])
    state, _, _ = run_conv("¿Cuál es la capital de Colombia?", llm, [])
    assert state["refused"] is True and state["answer"].startswith(prompts.REFUSAL_MESSAGE) and llm.calls == 1


def test_social_fallback_is_skipped_for_long_messages():
    llm = FakeLLM()
    state, _, _ = run_conv("Quisiera saber cuál es la distancia exacta entre la Tierra y la Luna en kilómetros hoy", llm, [])
    assert state["refused"] is True and llm.calls == 0


def test_social_classifier_garbage_defaults_to_refusal():
    llm = FakeLLM(["quizás tal vez"])
    state, _, _ = run_conv("¿Cuál es la capital de Colombia?", llm, [])
    assert state["refused"] is True


def test_partial_name_is_resolved_through_document_name():
    llm = FakeLLM(["Mordekaiser es un señor de la guerra [1]."])
    moruk = RetrievedChunk("Un señor de la guerra nigromante.", 0.9, "doc-9", "Mordekaiser.md")
    state, _, _ = run_conv("Cuál es la historia de Kaiser?", llm, [moruk])
    assert state["refused"] is False and llm.calls == 1


def test_refusal_suggests_what_to_ask():
    state, _, _ = run_conv("¿Cuál es la capital de Colombia?", FakeLLM(["OTRO"]), [])
    assert "Jinx" in state["answer"]
