"""Propose node — pick exact C++ strategy/router names into `chosen`."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.graph.state import AgentState
from app.tools.timeutil import last_n_session_days, session_range_ns


def _last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, BaseMessage) and msg.type == "human":
            return str(msg.content)
        if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return str(msg.get("content", ""))
    return ""


def _pick_name(candidates: list[str], text: str) -> str | None:
    lower = text.lower()
    # Prefer longer names first to avoid partial collisions
    for name in sorted(candidates, key=len, reverse=True):
        if name.lower() in lower:
            return name
    return candidates[0] if candidates else None


async def propose(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    _ = config
    intent = state.get("intent") or "unknown"
    text = _last_user_text(state)
    feedback = state.get("feedback") or ""

    settings = get_settings()
    capital = 1_00_000_00  # ₹1L default in paise
    lower = text.lower()
    n_days = 5 if any(w in lower for w in ("last 5", "last week", "past week", "5 session")) else 2
    days = last_n_session_days(n_days)
    from_ns, to_ns = session_range_ns(days[0], days[-1])

    if intent == "route":
        routers = list(state.get("router_candidates") or [])
        # Prefer a light router for agent hist unless user names one
        router = _pick_name(routers, text)
        if router is None:
            for preferred in ("live_run_testing_router", "default_router"):
                if preferred in routers:
                    router = preferred
                    break
            router = router or (routers[0] if routers else "default_router")
        # Prefer past closed day for hist
        anchor = days[-1]
        chosen = {
            "router": router,
            "anchor_date": anchor,
            "capital_paise": capital,
        }
        if feedback:
            chosen["feedback"] = feedback
        return {"chosen": chosen}

    # backtest / research / unknown → backtest shape when possible
    strategies = list(state.get("strategy_candidates") or [])
    strategy = _pick_name(strategies, text)
    tickers = list(state.get("tickers") or [])
    ticker = tickers[0] if tickers else "RELIANCE"
    if strategy is None:
        return {
            "error": "no strategy candidates from C++",
            "chosen": {},
        }
    chosen = {
        "strategy": strategy,
        "ticker": ticker,
        "from_ns": from_ns,
        "to_ns": to_ns,
        "capital_paise": capital,
        "session_from": days[0],
        "session_to": days[-1],
    }
    if feedback:
        # Soft iterate: keep same shape; future: LLM could change strategy
        chosen["feedback"] = feedback
    _ = settings
    return {"chosen": chosen, "error": None}
