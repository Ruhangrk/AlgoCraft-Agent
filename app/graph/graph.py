"""Build and compile the Phase A LangGraph."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.classify import classify_intent
from app.graph.nodes.evaluate import evaluate_node
from app.graph.nodes.execute import execute
from app.graph.nodes.propose import propose
from app.graph.nodes.research import research
from app.graph.nodes.respond import respond
from app.graph.state import AgentState


def _route_after_evaluate(state: AgentState) -> Literal["propose", "respond"]:
    if state.get("_retry"):
        return "propose"
    return "respond"


def build_graph() -> Any:
    g: StateGraph = StateGraph(AgentState)
    g.add_node("classify_intent", classify_intent)
    g.add_node("research", research)
    g.add_node("propose", propose)
    g.add_node("execute", execute)
    g.add_node("evaluate", evaluate_node)
    g.add_node("respond", respond)

    g.add_edge(START, "classify_intent")
    g.add_edge("classify_intent", "research")
    g.add_edge("research", "propose")
    g.add_edge("propose", "execute")
    g.add_edge("execute", "evaluate")
    g.add_conditional_edges(
        "evaluate",
        _route_after_evaluate,
        {"propose": "propose", "respond": "respond"},
    )
    g.add_edge("respond", END)
    return g.compile()


_compiled = None


def get_graph() -> Any:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled
