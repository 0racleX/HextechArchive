from typing import TypedDict


class AgentState(TypedDict, total=False):
    question: str
    user_id: str
    conversation_id: str
    intent: str
    chunks: list
    context_ok: bool
    answer: str
    sources: list
    refused: bool
