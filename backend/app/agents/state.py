from typing import TypedDict


class AgentState(TypedDict, total=False):
    question: str
    original_question: str   # lo que escribió el usuario cuando la pregunta se reformula (peticiones aleatorias)
    user_id: str
    conversation_id: str
    intent: str
    catalog: dict             # petición de catálogo detectada: {"kind", "subject", "letter"}
    chunks: list
    context_ok: bool
    answer: str
    sources: list
    refused: bool
