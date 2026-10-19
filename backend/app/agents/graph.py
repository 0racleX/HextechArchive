from langgraph.graph import END, START, StateGraph

from app.agents.nodes import make_nodes
from app.agents.state import AgentState


def _route_intent(state):
    intent = state["intent"]
    if intent == "ok":
        return "retrieve"
    if intent == "catalog":
        return "pick_topic" if state["catalog"]["kind"].startswith("random") else "catalog_answer"
    return "refuse"


def build_graph(retriever, llm, save_history, threshold: float, catalog=None, rng=None):
    n = make_nodes(retriever, llm, save_history, threshold, catalog=catalog, rng=rng)
    g = StateGraph(AgentState)
    g.add_node("validate_intent", n.validate_intent)
    g.add_node("pick_topic", n.pick_topic)
    g.add_node("catalog_answer", n.catalog_answer)
    g.add_node("retrieve", n.retrieve)
    g.add_node("grade_context", n.grade_context)
    g.add_node("generate", n.generate)
    g.add_node("social", n.social)
    g.add_node("refuse", n.refuse)
    g.add_node("save_history", n.save)

    g.add_edge(START, "validate_intent")
    g.add_conditional_edges(
        "validate_intent", _route_intent,
        {"retrieve": "retrieve", "pick_topic": "pick_topic", "catalog_answer": "catalog_answer", "refuse": "refuse"},
    )
    g.add_edge("pick_topic", "retrieve")
    g.add_edge("retrieve", "grade_context")
    g.add_conditional_edges(
        "grade_context",
        lambda s: "generate" if s["context_ok"] else "social",
        {"generate": "generate", "social": "social"},
    )
    for node in ("generate", "social", "catalog_answer", "refuse"):
        g.add_edge(node, "save_history")
    g.add_edge("save_history", END)
    return g.compile()
