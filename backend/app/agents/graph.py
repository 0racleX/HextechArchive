from langgraph.graph import END, START, StateGraph

from app.agents.nodes import make_nodes
from app.agents.state import AgentState


def build_graph(retriever, llm, save_history, threshold: float):
    n = make_nodes(retriever, llm, save_history, threshold)
    g = StateGraph(AgentState)
    g.add_node("validate_intent", n.validate_intent)
    g.add_node("retrieve", n.retrieve)
    g.add_node("grade_context", n.grade_context)
    g.add_node("generate", n.generate)
    g.add_node("refuse", n.refuse)
    g.add_node("save_history", n.save)

    g.add_edge(START, "validate_intent")
    g.add_conditional_edges(
        "validate_intent",
        lambda s: "retrieve" if s["intent"] == "ok" else "refuse",
        {"retrieve": "retrieve", "refuse": "refuse"},
    )
    g.add_edge("retrieve", "grade_context")
    g.add_conditional_edges(
        "grade_context",
        lambda s: "generate" if s["context_ok"] else "refuse",
        {"generate": "generate", "refuse": "refuse"},
    )
    g.add_edge("generate", "save_history")
    g.add_edge("refuse", "save_history")
    g.add_edge("save_history", END)
    return g.compile()
