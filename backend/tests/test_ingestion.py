import io

from pypdf import PdfWriter

from app.services.ingestion import IngestionService


class FakeStore:
    def __init__(self):
        self.chunks = []
        self.status = {}

    def add_chunks(self, document_id, chunks, embeddings):
        assert len(chunks) == len(embeddings)
        self.chunks.append((document_id, chunks))

    def set_status(self, document_id, status, error=None):
        self.status[document_id] = (status, error)


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]


class BrokenEmbedder:
    def embed_documents(self, texts):
        raise ConnectionError("ollama down")


def test_ingest_text_marks_ready():
    store = FakeStore()
    IngestionService(store, FakeEmbedder()).ingest("d1", "a.txt", ("Jinx " * 300).encode())
    assert store.status["d1"] == ("ready", None)
    assert store.chunks and store.chunks[0][0] == "d1"


def test_ingest_blank_pdf_marks_error_without_chunks():
    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buf)
    store = FakeStore()
    IngestionService(store, FakeEmbedder()).ingest("d2", "scan.pdf", buf.getvalue())
    status, error = store.status["d2"]
    assert status == "error"
    assert "texto" in error.lower()
    assert store.chunks == []


def test_ingest_embedder_failure_marks_error():
    store = FakeStore()
    IngestionService(store, BrokenEmbedder()).ingest("d3", "a.txt", b"contenido valido")
    assert store.status["d3"][0] == "error"
