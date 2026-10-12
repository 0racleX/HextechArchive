import logging

from app.loaders.chunking import split_text
from app.loaders.extract import extract_text

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, store, embedder, chunk_size: int = 800, overlap: int = 120):
        self.store = store
        self.embedder = embedder
        self.chunk_size = chunk_size
        self.overlap = overlap

    def ingest(self, document_id: str, filename: str, data: bytes) -> bool:
        """True si el documento quedó 'ready'; False si terminó en 'error'."""
        try:
            text = extract_text(filename, data)
            if not text.strip():
                raise ValueError("El documento no contiene texto extraíble")
            chunks = split_text(text, self.chunk_size, self.overlap)
            embeddings = self.embedder.embed_documents(chunks)
            self.store.add_chunks(document_id, chunks, embeddings)
            self.store.set_status(document_id, "ready")
            return True
        except Exception as exc:
            logger.exception("Falló la ingesta de %s", filename)
            self.store.set_status(document_id, "error", str(exc)[:300])
            return False
