"""Recuperación con prioridad por nombre.

La búsqueda por similitud sola puede dejar fuera el fragmento clave (p. ej. la 'Historia' de un campeón
cuando la pregunta es 'háblame de Briar, su historia'). Si la pregunta nombra un documento visible para
el usuario, se añaden primero los mejores fragmentos de ese documento y se completa con la búsqueda general.

El nombre puede escribirse exacto, parcial ('Kaiser' -> Mordekaiser) o con errores ('Jinks' -> Jinx); se usa
el mejor nivel de coincidencia disponible para no mezclar vecinos parecidos ('Sona' no arrastra a 'Sion').
"""
from app.agents.lexical import document_match_level

NAMED_DOC_CHUNKS = 3


def build_retriever(store, embedder, top_k: int):
    def retriever(question: str, user_id: str):
        vector = embedder.embed_query(question)
        general = store.search(vector, user_id, top_k)
        levels = {
            d.id: document_match_level(d.name, question)
            for d in store.list_documents(user_id) if d.status == "ready"
        }
        best = max(levels.values(), default=0)
        ids = [doc_id for doc_id, lv in levels.items() if lv == best] if best else []
        if not ids:
            return general
        named = store.search_documents(vector, user_id, ids, NAMED_DOC_CHUNKS)
        merged, seen = [], set()
        for chunk in [*named, *general]:
            key = (chunk.document_id, chunk.content)
            if key not in seen:
                seen.add(key)
                merged.append(chunk)
        return merged[:top_k]

    return retriever
