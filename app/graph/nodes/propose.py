"""Propose node — pick exact C++ strategy/router names into `chosen`."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.graph.nodes._common import last_user_text
from app.graph.nodes.entities import (
    extract_tickers,
    match_catalog_name,
    parse_user_date,
)
from app.graph.state import AgentState
from app.graph.thinking import thought
from app.tools.timeutil import last_n_session_days, session_range_ns


async def propose(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    _ = config
    intent = state.get("intent") or "unknown"
    text = last_user_text(state)
    feedback = state.get("feedback") or ""

    settings = get_settings()
    capital = 1_00_000_00
    lower = text.lower()
    n_days = 5 if any(w in lower for w in ("last 5", "last week", "past week", "5 session")) else 2

    user_day = parse_user_date(text)
    if user_day:
        days = [user_day]
        from_ns, to_ns = session_range_ns(user_day, user_day)
    else:
        days = last_n_session_days(n_days)
        from_ns, to_ns = session_range_ns(days[0], days[-1])

    if intent == "route":
        routers = list(state.get("router_candidates") or [])
        router = match_catalog_name(text, routers)
        if router is None:
            for preferred in ("live_run_testing_router", "default_router"):
                if preferred in routers:
                    router = preferred
                    break
            router = router or (routers[0] if routers else "default_router")
        anchor = days[-1]
        chosen = {
            "router": router,
            "anchor_date": anchor,
            "capital_paise": capital,
        }
        if feedback:
            chosen["feedback"] = feedback
        return {
            "chosen": chosen,
            **thought(
                "propose",
                f"Hist/route plan: router={router}, anchor={anchor}, capital_paise={capital}.",
                phase="decide",
                data=chosen,
            ),
        }

    strategies = list(state.get("strategy_candidates") or [])
    strategy = match_catalog_name(text, strategies)
    if strategy is None and state.get("topic_strategy"):
        strategy = match_catalog_name(str(state["topic_strategy"]), strategies)
    tickers = list(state.get("tickers") or []) or extract_tickers(text)
    ticker = tickers[0] if tickers else "RELIANCE"
    if strategy is None:
        return {
            "error": "no strategy candidates from C++",
            "chosen": {},
            **thought(
                "propose",
                "Cannot propose: no matching strategy name in message/catalog.",
                phase="decide",
            ),
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
        chosen["feedback"] = feedback
    _ = settings
    return {
        "chosen": chosen,
        "error": None,
        "tickers": tickers,
        **thought(
            "propose",
            f"Backtest plan: strategy={strategy}, ticker={ticker}, "
            f"sessions {days[0]}→{days[-1]}"
            + (f" (parsed date {user_day})" if user_day else f" ({len(days)}d)")
            + f", capital_paise={capital}.",
            phase="decide",
            data={k: v for k, v in chosen.items() if k != "feedback"},
        ),
    }
