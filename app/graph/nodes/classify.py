"""Classify user intent — thin alias to the production `route` agent."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.nodes.route import route_intent
from app.graph.state import AgentState


async def classify_intent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Backward-compatible name; routing lives in `route_intent`."""
    return await route_intent(state, config)
