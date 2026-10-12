import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.deps import get_agent, get_history_store
from app.security.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: UUID | None = None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("")
def chat(
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    agent=Depends(get_agent),
    history=Depends(get_history_store),
) -> StreamingResponse:
    created = False
    if body.conversation_id:
        conversation_id = str(body.conversation_id)
        if not history.owns_conversation(conversation_id, user.id):
            raise HTTPException(404, "Conversación no encontrada")
    else:
        conversation_id = history.create_conversation(user.id, body.question.strip()[:60])
        created = True

    def stream():
        final: dict = {}
        try:
            init = {"question": body.question, "user_id": user.id, "conversation_id": conversation_id}
            for mode, payload in agent.stream(init, stream_mode=["updates", "custom"]):
                if mode == "custom":
                    yield _sse({"type": "token", "text": payload["token"]})
                else:
                    for node, update in payload.items():
                        yield _sse({"type": "step", "node": node})
                        final.update(update or {})
            yield _sse({
                "type": "final",
                "answer": final.get("answer", ""),
                "sources": final.get("sources", []),
                "refused": bool(final.get("refused")),
                "conversation_id": conversation_id,
            })
        except Exception:
            logger.exception("Error ejecutando el agente")
            if created:
                try:
                    if not history.get_messages(conversation_id, user.id):
                        history.delete_conversation(conversation_id, user.id)
                except Exception:
                    logger.exception("No se pudo limpiar la conversación vacía")
            yield _sse({"type": "error", "message": "El agente no pudo responder en este momento. Intenta de nuevo en unos segundos."})

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
