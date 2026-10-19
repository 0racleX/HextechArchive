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

    def catalog(user_id: str) -> list[str]:
        """Nombres de los documentos listos que el usuario puede ver (corpus compartido + los suyos)."""
        return [d.name for d in store.list_documents(user_id) if d.status == "ready"]

    return build_graph(
        retriever, build_llm(s), make_history_saver(get_history_store()), s.similarity_threshold, catalog=catalog,
    )
