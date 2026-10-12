from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_history_store
from app.security.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/conversations", tags=["history"])


@router.get("")
def list_conversations(user: CurrentUser = Depends(get_current_user), history=Depends(get_history_store)) -> list[dict]:
    return history.list_conversations(user.id)


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    history=Depends(get_history_store),
) -> dict:
    messages = history.get_messages(str(conversation_id), user.id)
    if messages is None:
        raise HTTPException(404, "Conversación no encontrada")
    return {"id": str(conversation_id), "messages": messages}
