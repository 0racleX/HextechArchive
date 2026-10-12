from psycopg.types.json import Json

from app.repositories.models import DocumentRecord, RetrievedChunk


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"


class VectorStore:
    def __init__(self, pool):
        self.pool = pool

    def create_document(self, user_id: str | None, name: str, type_: str) -> str:
        with self.pool.connection() as conn:
            row = conn.execute(
                "insert into documents(user_id, name, type) values (%s, %s, %s) returning id",
                (user_id, name, type_),
            ).fetchone()
        return str(row["id"])

    def set_status(self, document_id: str, status: str, error: str | None = None) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                "update documents set status = %s, error = %s where id = %s",
                (status, error, document_id),
            )

    def add_chunks(self, document_id: str, chunks: list[str], embeddings: list[list[float]]) -> None:
        rows = [
            (document_id, text, Json({"index": i}), _vec(emb))
            for i, (text, emb) in enumerate(zip(chunks, embeddings))
        ]
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "insert into chunks(document_id, content, metadata, embedding) "
                    "values (%s, %s, %s, %s::vector)",
                    rows,
                )

    def search(self, embedding: list[float], user_id: str, k: int) -> list[RetrievedChunk]:
        vec = _vec(embedding)
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                select c.content, d.id as document_id, d.name as document_name,
                       1 - (c.embedding <=> %s::vector) as score
                from chunks c join documents d on d.id = c.document_id
                where d.status = 'ready' and (d.user_id is null or d.user_id = %s)
                order by c.embedding <=> %s::vector
                limit %s
                """,
                (vec, user_id, vec, k),
            ).fetchall()
        return [
            RetrievedChunk(r["content"], float(r["score"]), str(r["document_id"]), r["document_name"])
            for r in rows
        ]

    def list_documents(self, user_id: str) -> list[DocumentRecord]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "select id, name, type, status, error, created_at, user_id is null as shared "
                "from documents where user_id is null or user_id = %s order by created_at desc",
                (user_id,),
            ).fetchall()
        return [
            DocumentRecord(
                str(r["id"]), r["name"], r["type"], r["status"], r["error"],
                r["created_at"].isoformat(), r["shared"],
            )
            for r in rows
        ]

    def delete_document(self, document_id: str, user_id: str) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute(
                "delete from documents where id = %s and user_id = %s returning id",
                (document_id, user_id),
            ).fetchone()
        return row is not None

    def find_shared(self, name: str) -> str | None:
        with self.pool.connection() as conn:
            row = conn.execute(
                "select id from documents where user_id is null and name = %s", (name,)
            ).fetchone()
        return str(row["id"]) if row else None
