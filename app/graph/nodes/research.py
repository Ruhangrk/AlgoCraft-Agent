"""Research node — list strategies/routers from C++."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.nodes._common import get_client
from app.graph.state import AgentState
from app.graph.thinking import thought


async def research(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    client = get_client(config)
    strategies = await client.list_strategies()
    routers = await client.list_routers()

    notes_parts = [
        f"strategies({len(strategies)}): {', '.join(strategies[:12])}",
        f"routers: {', '.join(routers)}",
    ]
    tickers = list(state.get("tickers") or [])
    if tickers and hasattr(client, "search_instruments"):
        try:
            rows = await client.search_instruments(tickers[0], limit=5)
            notes_parts.append(f"instruments[{tickers[0]}]: {rows!r}"[:240])
        except Exception as exc:  # noqa: BLE001 — research is best-effort
            notes_parts.append(f"instrument search failed: {exc}")

    notes = " | ".join(notes_parts)
    intent = state.get("intent")
    route_hint = {
        "backtest": "next → propose/execute",
        "route": "next → propose/execute (hist)",
        "create": "next → create_interview / design",
        "discuss": "next → discuss",
    }.get(str(intent), "next → respond")

    return {
        "strategy_candidates": list(strategies),
        "router_candidates": list(routers),
        "research_notes": notes,
        "tickers": tickers,
        **thought(
            "research",
            f"Fetched C++ catalogs: {len(strategies)} strategies, {len(routers)} routers. "
            f"intent={intent} → {route_hint}. Notes: {notes[:320]}",
            phase="tool",
            data={
                "strategy_count": len(strategies),
                "router_count": len(routers),
                "intent": intent,
            },
        ),
    }
