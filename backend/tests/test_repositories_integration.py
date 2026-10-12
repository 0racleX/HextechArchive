import os
import uuid

import pytest

from app.repositories.db import make_pool
from app.repositories.history import HistoryStore
from app.repositories.vector_store import VectorStore

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL no definida")


@pytest.fixture
def pool():
    p = make_pool(URL)
    yield p
    p.close()


def vec(first: float) -> list[float]:
    v = [0.0] * 768
    v[0] = first
    v[1] = 1.0 - first
    return v


def test_search_is_isolated_per_user_but_includes_shared(pool):
    store = VectorStore(pool)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    doc_a = store.create_document(a, "a.txt", "txt")
    doc_b = store.create_document(b, "b.txt", "txt")
    shared = store.create_document(None, f"shared-{uuid.uuid4()}.md", "md")
    for doc, text in ((doc_a, "solo de A"), (doc_b, "solo de B"), (shared, "compartido")):
        store.add_chunks(doc, [text], [vec(0.9)])
        store.set_status(doc, "ready")
    try:
        contents = {c.content for c in store.search(vec(0.9), a, 10)}
        assert "solo de A" in contents and "compartido" in contents
        assert "solo de B" not in contents
        assert {d.id for d in store.list_documents(a)} >= {doc_a, shared}
        assert doc_b not in {d.id for d in store.list_documents(a)}
        assert store.delete_document(doc_b, a) is False   # no puede borrar ajenos
        assert store.delete_document(shared, a) is False  # ni el corpus compartido
    finally:
        for doc, owner in ((doc_a, a), (doc_b, b)):
            store.delete_document(doc, owner)
        with pool.connection() as conn:
            conn.execute("delete from documents where id = %s", (shared,))


def test_processing_documents_are_not_searchable(pool):
    store = VectorStore(pool)
    u = str(uuid.uuid4())
    doc = store.create_document(u, "p.txt", "txt")
    store.add_chunks(doc, ["pendiente"], [vec(0.5)])
    try:
        assert store.search(vec(0.5), u, 5) == []
    finally:
        store.delete_document(doc, u)


def test_conversations_are_private(pool):
    h = HistoryStore(pool)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    cid = h.create_conversation(a, "Hola")
    h.add_message(cid, "user", "¿Quién es Jinx?")
    h.add_message(cid, "assistant", "Una criminal", sources=[{"document": "Jinx.md"}], refused=False)
    assert h.owns_conversation(cid, a) is True
    assert h.owns_conversation(cid, b) is False
    assert h.get_messages(cid, b) is None
    msgs = h.get_messages(cid, a)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["sources"] == [{"document": "Jinx.md"}]
    assert cid in {c["id"] for c in h.list_conversations(a)}
    assert h.list_conversations(b) == []
    with pool.connection() as conn:
        conn.execute("delete from conversations where id = %s", (cid,))
