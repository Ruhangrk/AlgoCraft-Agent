"""Build and compile the production LangGraph (router-first)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.compile_loop import compile_loop
from app.graph.nodes.create_interview import create_interview
from app.graph.nodes.design_code import design_code
from app.graph.nodes.discuss import discuss
from app.graph.nodes.evaluate import evaluate_node
from app.graph.nodes.execute import execute
from app.graph.nodes.propose import propose
from app.graph.nodes.research import research
from app.graph.nodes.respond import respond
from app.graph.nodes.route import route_intent
from app.graph.state import AgentState


def _route_after_router(
    state: AgentState,
) -> Literal["research", "discuss", "create_interview", "respond"]:
    intent = state.get("intent")
    if intent in ("backtest", "route"):
        return "research"
    if intent == "discuss":
        return "discuss"
    if intent == "create":
        return "create_interview"
    # chat | clarify | legacy
    return "respond"


def _route_after_create(
    state: AgentState,
) -> Literal["design_code", "respond"]:
    if state.get("create_ready"):
        return "design_code"
    return "respond"


def _route_after_research(state: AgentState) -> Literal["propose"]:
    _ = state
    return "propose"


def _route_after_evaluate(state: AgentState) -> Literal["propose", "respond"]:
    if state.get("_retry"):
        return "propose"
    return "respond"


def build_graph() -> Any:
    g: StateGraph = StateGraph(AgentState)
    g.add_node("route", route_intent)
    g.add_node("research", research)
    g.add_node("discuss", discuss)
    g.add_node("create_interview", create_interview)
    g.add_node("propose", propose)
    g.add_node("execute", execute)
    g.add_node("evaluate", evaluate_node)
    g.add_node("design_code", design_code)
    g.add_node("compile_loop", compile_loop)
    g.add_node("respond", respond)

    g.add_edge(START, "route")
    g.add_conditional_edges(
        "route",
        _route_after_router,
        {
            "research": "research",
            "discuss": "discuss",
            "create_interview": "create_interview",
            "respond": "respond",
        },
    )
    g.add_edge("discuss", "respond")
    g.add_conditional_edges(
        "create_interview",
        _route_after_create,
        {"design_code": "design_code", "respond": "respond"},
    )
    g.add_edge("research", "propose")
    g.add_edge("propose", "execute")
    g.add_edge("execute", "evaluate")
    g.add_conditional_edges(
        "evaluate",
        _route_after_evaluate,
        {"propose": "propose", "respond": "respond"},
    )
    g.add_edge("design_code", "compile_loop")
    g.add_edge("compile_loop", "respond")
    g.add_edge("respond", END)
    return g.compile()


_compiled = None


def get_graph() -> Any:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def reset_graph_cache() -> None:
    global _compiled
    _compiled = None
