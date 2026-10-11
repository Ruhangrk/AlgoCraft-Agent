"""Shared helpers for graph nodes."""

from __future__ import annotations

from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState
from app.tools.algocraft_client import AlgocraftClient


def llm_content_text(content: Any) -> str:
    """Normalize chat-model content (str | list blocks) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            else:
                text = getattr(block, "text", None)
                parts.append(str(text if text is not None else block))
        return "".join(parts).strip()
    return str(content).strip()


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


def get_llm(config: RunnableConfig | None) -> BaseChatModel | None:
    llm = configurable(config).get("llm")
    return cast(BaseChatModel | None, llm)


def get_client(config: RunnableConfig | None) -> AlgocraftClient:
    client = configurable(config).get("algocraft")
    if client is None:
        raise RuntimeError("configurable['algocraft'] client required")
    # Duck-typed test fakes are allowed at runtime; cast keeps IDE/refs honest.
    return cast(AlgocraftClient, client)
