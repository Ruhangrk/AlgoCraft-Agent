"""LangGraph AgentState for AlgoCraft-Agent."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    session_id: str
    user_jwt: str
    workbook_id: int | None
    llm_provider: str
    llm_model: str
    llm_temperature: float

    intent: Literal[
        "chat",
        "discuss",
        "backtest",
        "route",
        "create",
        "clarify",
        # legacy aliases still accepted in old tests / cards
        "research",
        "codegen_strategy",
        "explain",
        "unknown",
    ]
    tickers: list[str]
    strategy_candidates: list[str]
    router_candidates: list[str]
    research_notes: str

    topic_strategy: str | None
    create_draft: dict[str, Any]
    create_ready: bool
    interview_prompt: str | None
    discuss_summary: str | None

    chosen: dict[str, Any]
    cpp_results: dict[str, Any]
    metrics: dict[str, Any]
    eval_verdict: Literal["pass", "weak", "fail", "need_human", "error"]
    feedback: str
    iteration: int
    max_iterations: int
    compile_attempts: int
    pending_human: Literal["none", "promote", "activate"]
    error: str | None
    card: dict[str, Any]
    response_text: str
    _retry: bool
    thinking: Annotated[list[dict[str, Any]], operator.add]
