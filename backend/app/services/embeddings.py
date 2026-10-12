from langchain_ollama import OllamaEmbeddings

BATCH = 16


class Embedder:
    """nomic-embed-text requiere prefijos distintos para documentos y consultas."""

    def __init__(self, model: str, base_url: str):
        self._emb = OllamaEmbeddings(model=model, base_url=base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            batch = [f"search_document: {t}" for t in texts[i : i + BATCH]]
            out.extend(self._emb.embed_documents(batch))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._emb.embed_query(f"search_query: {text}")
