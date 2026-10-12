from langchain_ollama import ChatOllama

from app.config import Settings


def build_llm(settings: Settings) -> ChatOllama:
    return ChatOllama(
        model=settings.chat_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        num_ctx=2048,
        num_predict=400,
        keep_alive="24h",
    )
