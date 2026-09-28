"""Classify user intent (rules-first; optional LLM later)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import BaseMessage

from app.graph.state import AgentState


def _last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, BaseMessage):
            if msg.type == "human":
                return str(msg.content)
        elif isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return str(msg.get("content", ""))
        elif isinstance(msg, dict) and msg.get("type") == "human":
            return str(msg.get("content", ""))
    return ""


_TICKER_RE = re.compile(r"\b([A-Z]{2,12})\b")


def classify_intent(state: AgentState) -> dict[str, Any]:
    text = _last_user_text(state)
    lower = text.lower()

    tickers = [
        t
        for t in _TICKER_RE.findall(text)
        if t not in {"POST", "GET", "HTTP", "API", "IST", "NSE", "LLM"}
    ]

    intent: str
    if "codegen" in lower or "generate strategy" in lower or "write a strategy" in lower:
        intent = "codegen_strategy"
    elif "backtest" in lower:
        intent = "backtest"
    elif any(w in lower for w in ("router", "hist run", "route ", "routing")):
        intent = "route"
    elif any(w in lower for w in ("explain", "what is", "how does")):
        intent = "explain"
    elif any(w in lower for w in ("research", "list strateg", "what strateg")):
        intent = "research"
    else:
        # Default trading asks → backtest when a ticker-like token appears
        intent = "backtest" if tickers else "unknown"

    out: dict[str, Any] = {"intent": intent}  # type: ignore[dict-item]
    if tickers:
        out["tickers"] = tickers
    if "max_iterations" not in state:
        from app.config import get_settings

        out["max_iterations"] = get_settings().agent_max_iterations
    if "iteration" not in state:
        out["iteration"] = 0
    return out
