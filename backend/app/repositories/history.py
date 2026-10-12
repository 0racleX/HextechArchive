from psycopg.types.json import Json


class HistoryStore:
    def __init__(self, pool):
        self.pool = pool

    def create_conversation(self, user_id: str, title: str) -> str:
        with self.pool.connection() as conn:
            row = conn.execute(
                "insert into conversations(user_id, title) values (%s, %s) returning id",
                (user_id, title),
            ).fetchone()
        return str(row["id"])

    def owns_conversation(self, conversation_id: str, user_id: str) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute(
                "select 1 as ok from conversations where id = %s and user_id = %s",
                (conversation_id, user_id),
            ).fetchone()
        return row is not None

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute(
                "delete from conversations where id = %s and user_id = %s returning id",
                (conversation_id, user_id),
            ).fetchone()
        return row is not None

    def add_message(self, conversation_id: str, role: str, content: str,
                    sources: list | None = None, refused: bool = False) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                "insert into messages(conversation_id, role, content, sources, refused) "
                "values (%s, %s, %s, %s, %s)",
                (conversation_id, role, content, Json(sources) if sources is not None else None, refused),
            )

    def list_conversations(self, user_id: str) -> list[dict]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "select id, title, created_at from conversations "
                "where user_id = %s order by created_at desc",
                (user_id,),
            ).fetchall()
        return [
            {"id": str(r["id"]), "title": r["title"], "created_at": r["created_at"].isoformat()}
            for r in rows
        ]

    def get_messages(self, conversation_id: str, user_id: str) -> list[dict] | None:
        if not self.owns_conversation(conversation_id, user_id):
            return None
        with self.pool.connection() as conn:
            rows = conn.execute(
                "select role, content, sources, refused, created_at from messages "
                "where conversation_id = %s order by id",
                (conversation_id,),
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "sources": r["sources"],
             "refused": r["refused"], "created_at": r["created_at"].isoformat()}
            for r in rows
        ]
