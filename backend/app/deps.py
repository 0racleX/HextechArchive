from functools import lru_cache

from app.config import get_settings
from app.repositories.db import make_pool
from app.repositories.history import HistoryStore
from app.repositories.vector_store import VectorStore
from app.services.embeddings import Embedder
from app.services.ingestion import IngestionService


@lru_cache
def get_pool():
    return make_pool(get_settings().database_url)


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore(get_pool())


@lru_cache
def get_history_store() -> HistoryStore:
    return HistoryStore(get_pool())


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    return Embedder(s.embed_model, s.ollama_base_url)


@lru_cache
def get_ingestion() -> IngestionService:
    return IngestionService(get_vector_store(), get_embedder())
