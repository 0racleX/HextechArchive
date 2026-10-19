import threading
import time
from functools import lru_cache

from app.agents.graph import build_graph
from app.agents.llm import build_llm
from app.agents.retrieval import build_retriever
from app.config import get_settings
from app.repositories.db import make_pool
from app.repositories.history import HistoryStore
from app.repositories.vector_store import VectorStore
from app.services.chat import make_history_saver
from app.services.embeddings import Embedder
from app.services.ingestion import IngestionService


class CatalogCache:
    """Caché con TTL del catálogo por usuario; se invalida al subir o borrar documentos."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._items: dict[str, tuple[float, list[str]]] = {}
        self._lock = threading.Lock()

    def get(self, user_id: str, ttl: float, load) -> list[str]:
        if ttl <= 0:
            return load(user_id)
        now = self._clock()
        with self._lock:
            hit = self._items.get(user_id)
            if hit and now - hit[0] < ttl:
                return list(hit[1])
        names = load(user_id)
        with self._lock:
            self._items[user_id] = (now, list(names))
        return names

    def invalidate(self, user_id: str | None = None) -> None:
        with self._lock:
            if user_id is None:
                self._items.clear()
            else:
                self._items.pop(user_id, None)


catalog_cache = CatalogCache()


def make_catalog(store, ttl: float, cache: CatalogCache = catalog_cache):
    def load(user_id: str) -> list[str]:
        return [d.name for d in store.list_documents(user_id) if d.status == "ready"]

    def catalog(user_id: str) -> list[str]:
        """Nombres de los documentos listos que el usuario puede ver (corpus compartido + los suyos)."""
        return cache.get(user_id, ttl, load)

    return catalog


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


@lru_cache
def get_agent():
    s = get_settings()
    store = get_vector_store()
    retriever = build_retriever(store, get_embedder(), s.top_k)

    catalog = make_catalog(store, s.catalog_cache_ttl_seconds)

    return build_graph(
        retriever, build_llm(s), make_history_saver(get_history_store()), s.similarity_threshold, catalog=catalog,
    )
