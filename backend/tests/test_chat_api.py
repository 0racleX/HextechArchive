import json
import uuid

import pytest

from app.agents.graph import build_graph
from app.deps import get_agent, get_history_store
from app.main import app
from app.repositories.models import RetrievedChunk
from app.services.chat import make_history_saver
from tests.conftest import make_token
from tests.test_agent_graph import FakeLLM


class FakeHistory:
    def __init__(self):
        self.convs: dict[str, dict] = {}
        self.msgs: dict[str, list[dict]] = {}

    def create_conversation(self, user_id, title):
        cid = str(uuid.uuid4())
        self.convs[cid] = {"user_id": user_id, "title": title}
        self.msgs[cid] = []
        return cid

    def owns_conversation(self, cid, user_id):
        return cid in self.convs and self.convs[cid]["user_id"] == user_id

    def delete_conversation(self, cid, user_id):
        if not self.owns_conversation(cid, user_id):
            return False
        del self.convs[cid], self.msgs[cid]
        return True

    def add_message(self, cid, role, content, sources=None, refused=False):
        self.msgs[cid].append({"role": role, "content": content, "sources": sources,
                               "refused": refused, "created_at": "2026-01-01T00:00:00"})

    def list_conversations(self, user_id):
        return [{"id": i, "title": c["title"], "created_at": "2026-01-01T00:00:00"}
                for i, c in self.convs.items() if c["user_id"] == user_id]

    def get_messages(self, cid, user_id):
        return self.msgs[cid] if self.owns_conversation(cid, user_id) else None


def headers(user="user-a"):
    return {"Authorization": f"Bearer {make_token(sub=user)}"}


def sse_events(response):
    return [json.loads(block[6:]) for block in response.text.split("\n\n") if block.startswith("data: ")]


@pytest.fixture
def history():
    h = FakeHistory()
    app.dependency_overrides[get_history_store] = lambda: h
    return h


def install_agent(history, llm, chunks):
    graph = build_graph(lambda q, u: chunks, llm, make_history_saver(history), 0.55)
    app.dependency_overrides[get_agent] = lambda: graph


GOOD = [RetrievedChunk("Jinx es una criminal de Zaun.", 0.9, "d1", "Jinx.md")]


def test_chat_requires_auth(client):
    assert client.post("/chat", json={"question": "hola"}).status_code == 401
    assert client.get("/conversations").status_code == 401
    assert client.get(f"/conversations/{uuid.uuid4()}").status_code == 401


def test_chat_streams_tokens_and_final_and_persists(client, history):
    install_agent(history, FakeLLM(["SI", "Jinx es una criminal de Zaun [1]."]), GOOD)
    r = client.post("/chat", json={"question": "¿Quién es Jinx?"}, headers=headers())
    assert r.status_code == 200
    events = sse_events(r)
    types = [e["type"] for e in events]
    assert "step" in types and "token" in types and types[-1] == "final"
    final = events[-1]
    assert final["refused"] is False and final["sources"][0]["document"] == "Jinx.md"
    msgs = history.msgs[final["conversation_id"]]
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_chat_refusal_is_flagged(client, history):
    install_agent(history, FakeLLM(), [])
    final = sse_events(client.post("/chat", json={"question": "¿Receta de sushi?"}, headers=headers()))[-1]
    assert final["refused"] is True and "No tengo suficiente información" in final["answer"]


def test_chat_continues_existing_conversation(client, history):
    install_agent(history, FakeLLM(), [])
    first = sse_events(client.post("/chat", json={"question": "¿Receta de sushi?"}, headers=headers()))[-1]
    cid = first["conversation_id"]
    second = sse_events(client.post("/chat", json={"question": "¿Otra receta?", "conversation_id": cid},
                                    headers=headers()))[-1]
    assert second["conversation_id"] == cid
    assert len(history.msgs[cid]) == 4


def test_cannot_use_foreign_conversation(client, history):
    install_agent(history, FakeLLM(), [])
    cid = history.create_conversation("user-a", "privada")
    r = client.post("/chat", json={"question": "¿Hola qué tal?", "conversation_id": cid}, headers=headers("user-b"))
    assert r.status_code == 404
    assert client.get(f"/conversations/{cid}", headers=headers("user-b")).status_code == 404
    assert client.get("/conversations", headers=headers("user-b")).json() == []


@pytest.mark.parametrize("body", [{"question": ""}, {"question": "x" * 1001}, {}])
def test_invalid_question_payload_is_422(client, history, body):
    install_agent(history, FakeLLM(), [])
    assert client.post("/chat", json=body, headers=headers()).status_code == 422


def test_ollama_down_emits_friendly_error_event(client, history):
    class DownLLM:
        def invoke(self, prompt):
            raise ConnectionError("connection refused")

        def stream(self, prompt):
            raise ConnectionError("connection refused")

    install_agent(history, DownLLM(), GOOD)
    r = client.post("/chat", json={"question": "¿Quién es Jinx?"}, headers=headers())
    assert r.status_code == 200
    last = sse_events(r)[-1]
    assert last["type"] == "error"
    assert "connection refused" not in last["message"]
    assert "Traceback" not in r.text


def test_history_endpoints_return_messages(client, history):
    install_agent(history, FakeLLM(), [])
    cid = sse_events(client.post("/chat", json={"question": "¿Receta de sushi?"}, headers=headers()))[-1]["conversation_id"]
    listing = client.get("/conversations", headers=headers()).json()
    assert [c["id"] for c in listing] == [cid]
    detail = client.get(f"/conversations/{cid}", headers=headers()).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


class _DownLLM:
    def invoke(self, prompt):
        raise ConnectionError("connection refused")

    def stream(self, prompt):
        raise ConnectionError("connection refused")


def test_failure_on_new_conversation_leaves_no_empty_conversation(client, history):
    install_agent(history, _DownLLM(), GOOD)
    r = client.post("/chat", json={"question": "¿Quién es Jinx?"}, headers=headers())
    assert sse_events(r)[-1]["type"] == "error"
    assert client.get("/conversations", headers=headers()).json() == []


def test_failure_on_existing_conversation_does_not_delete_it(client, history):
    install_agent(history, _DownLLM(), GOOD)
    cid = history.create_conversation("user-a", "previa")
    r = client.post("/chat", json={"question": "¿Quién es Jinx?", "conversation_id": cid}, headers=headers())
    assert sse_events(r)[-1]["type"] == "error"
    assert [c["id"] for c in client.get("/conversations", headers=headers()).json()] == [cid]


def test_cleanup_failure_does_not_mask_error_event(client, history):
    install_agent(history, _DownLLM(), GOOD)

    def boom(*a, **k):
        raise RuntimeError("db down")

    history.delete_conversation = boom
    r = client.post("/chat", json={"question": "¿Quién es Jinx?"}, headers=headers())
    last = sse_events(r)[-1]
    assert last["type"] == "error" and "db down" not in r.text
