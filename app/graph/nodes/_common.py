"""Shared helpers for graph nodes."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState


def last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, BaseMessage) and msg.type == "human":
            return str(msg.content)
        if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return str(msg.get("content", ""))
        if isinstance(msg, dict) and msg.get("type") == "human":
            return str(msg.get("content", ""))
    return ""


def configurable(config: RunnableConfig | None) -> dict[str, Any]:
    return dict((config or {}).get("configurable") or {})


def get_llm(config: RunnableConfig | None) -> Any | None:
    return configurable(config).get("llm")


def get_client(config: RunnableConfig | None) -> Any:
    client = configurable(config).get("algocraft")
    if client is None:
        raise RuntimeError("configurable['algocraft'] client required")
    return client
