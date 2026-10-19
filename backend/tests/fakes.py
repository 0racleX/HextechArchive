import uuid

from app.repositories.models import DocumentRecord, RetrievedChunk


class FakeStore:
    """Implementación en memoria de VectorStore para tests."""

    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.chunks: dict[str, list[tuple[str, list[float]]]] = {}

    def create_document(self, user_id, name, type_, content_hash=None):
        doc_id = str(uuid.uuid4())
        self.docs[doc_id] = {"user_id": user_id, "name": name, "type": type_,
                             "status": "processing", "error": None, "content_hash": content_hash}
        return doc_id

    def find_by_hash(self, user_id, content_hash):
        for d in self.docs.values():
            if d["user_id"] == user_id and d.get("content_hash") == content_hash and d["status"] != "error":
                return d["name"]
        return None

    def count_user_documents(self, user_id):
        return sum(1 for d in self.docs.values() if d["user_id"] == user_id)

    def set_status(self, document_id, status, error=None):
        self.docs[document_id].update(status=status, error=error)

    def add_chunks(self, document_id, chunks, embeddings):
        self.chunks[document_id] = list(zip(chunks, embeddings))

    def search(self, embedding, user_id, k):
        out = []
        for doc_id, pairs in self.chunks.items():
            d = self.docs[doc_id]
            if d["status"] == "ready" and d["user_id"] in (None, user_id):
                out += [RetrievedChunk(t, 0.9, doc_id, d["name"]) for t, _ in pairs]
        return out[:k]

    def list_documents(self, user_id):
        return [
            DocumentRecord(i, d["name"], d["type"], d["status"], d["error"], "2026-01-01T00:00:00", d["user_id"] is None)
            for i, d in self.docs.items() if d["user_id"] in (None, user_id)
        ]

    def delete_document(self, document_id, user_id):
        d = self.docs.get(document_id)
        if d and d["user_id"] == user_id:
            del self.docs[document_id]
            self.chunks.pop(document_id, None)
            return True
        return False


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768
