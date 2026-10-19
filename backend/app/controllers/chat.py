import json
import logging
import queue
import threading
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.controllers.ratelimit import limit_chat
from app.deps import get_agent, get_history_store
from app.security.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

HEARTBEAT_SECONDS = 10  # sin eventos durante este tiempo se emite un comentario SSE ": ping"
_QUEUE_SIZE = 256
_DONE = object()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: UUID | None = None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _event_stream(body: ChatRequest, user: CurrentUser, agent, history, conversation_id: str, created: bool):
    final: dict = {}
    q: queue.Queue = queue.Queue(maxsize=_QUEUE_SIZE)
    stop = threading.Event()  # se activa si el cliente se desconecta

    def put(item) -> bool:
        while not stop.is_set():
            try:
                q.put(item, timeout=0.5)
                return True
            except queue.Full:
                continue
        return False

    def worker():
        init = {"question": body.question, "user_id": user.id, "conversation_id": conversation_id}
        gen = None
        try:
            gen = agent.stream(init, stream_mode=["updates", "custom"])
            for item in gen:
                if stop.is_set() or not put(("item", item)):
                    break
        except Exception as exc:
            put(("error", exc))
        finally:
            close = getattr(gen, "close", None)
            if close:
                try:
                    close()  # libera el modelo (Ollama atiende una sola petición a la vez)
                except Exception:
                    logger.exception("No se pudo cerrar el generador del agente")
            put((_DONE, None))

    threading.Thread(target=worker, daemon=True).start()
    try:
        while True:
            try:
                kind, value = q.get(timeout=HEARTBEAT_SECONDS)
            except queue.Empty:
                yield ": ping\n\n"  # latido: mantiene viva la conexión durante inferencias lentas
                continue
            if kind is _DONE:
                break
            if kind == "error":
                raise value
            mode, payload = value
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
    finally:
        stop.set()


@router.post("")
def chat(
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    agent=Depends(get_agent),
    history=Depends(get_history_store),
    _rate: None = Depends(limit_chat),
) -> StreamingResponse:
    created = False
    if body.conversation_id:
        conversation_id = str(body.conversation_id)
        if not history.owns_conversation(conversation_id, user.id):
            raise HTTPException(404, "Conversación no encontrada")
    else:
        conversation_id = history.create_conversation(user.id, body.question.strip()[:60])
        created = True

    return StreamingResponse(
        _event_stream(body, user, agent, history, conversation_id, created), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
