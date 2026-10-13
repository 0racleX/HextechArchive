from app.agents.retrieval import build_retriever
from app.repositories.models import DocumentRecord, RetrievedChunk


def rc(doc_id, name, text, score):
    return RetrievedChunk(text, score, doc_id, name)


def rec(doc_id, name, status="ready"):
    return DocumentRecord(doc_id, name, "md", status, None, "2026-01-01T00:00:00", True)


class Store:
    def __init__(self, general, by_doc, docs):
        self.general, self.by_doc, self.docs = general, by_doc, docs
        self.calls = []

    def search(self, embedding, user_id, k):
        self.calls.append(("search", user_id, k))
        return self.general[:k]

    def list_documents(self, user_id):
        self.calls.append(("list", user_id))
        return self.docs

    def search_documents(self, embedding, user_id, document_ids, k):
        self.calls.append(("search_documents", user_id, tuple(document_ids), k))
        return [c for c in self.by_doc if c.document_id in document_ids][:k]


class Emb:
    def embed_query(self, text):
        return [0.1] * 768


GENERAL = [rc("zone", "Region-Islas.md", f"texto {i}", 0.70 - i / 100) for i in range(5)]
BRIAR = [rc("b", "Briar.md", "## Historia de Briar", 0.66), rc("b", "Briar.md", "## Pasiva", 0.70)]
DOCS = [rec("b", "Briar.md"), rec("zone", "Region-Islas.md"), rec("p", "Pendiente.md", status="processing")]


def test_named_document_chunks_come_first_and_total_is_capped():
    store = Store(GENERAL, BRIAR, DOCS)
    out = build_retriever(store, Emb(), top_k=5)("Hablame mas sobre Briar, su historia", "u1")
    assert [c.document_id for c in out[:2]] == ["b", "b"]
    assert len(out) == 5
    assert ("search_documents", "u1", ("b",), 3) in store.calls


def test_no_named_document_keeps_plain_similarity_results():
    store = Store(GENERAL, BRIAR, DOCS)
    out = build_retriever(store, Emb(), top_k=5)("¿Cuál es la capital de Colombia?", "u1")
    assert out == GENERAL
    assert not any(c[0] == "search_documents" for c in store.calls)


def test_duplicates_are_removed():
    dup = [BRIAR[0]]
    store = Store(dup + GENERAL[:4], BRIAR, DOCS)
    out = build_retriever(store, Emb(), top_k=5)("quien es briar", "u1")
    assert len({(c.document_id, c.content) for c in out}) == len(out)


def test_documents_not_ready_are_never_used():
    store = Store(GENERAL, BRIAR, [rec("p", "Briar.md", status="processing")])
    out = build_retriever(store, Emb(), top_k=5)("quien es briar", "u1")
    assert out == GENERAL
