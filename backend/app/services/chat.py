def make_history_saver(history):
    """Devuelve el callback `save_history` que usa el nodo final del grafo."""

    def save(state: dict) -> None:
        cid = state["conversation_id"]
        history.add_message(cid, "user", state["question"])
        history.add_message(
            cid, "assistant", state["answer"],
            sources=state.get("sources") or [], refused=bool(state.get("refused")),
        )

    return save
