"""Research node — list strategies/routers from C++."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState


def _client(config: RunnableConfig) -> Any:
    conf = (config or {}).get("configurable") or {}
    client = conf.get("algocraft")
    if client is None:
        raise RuntimeError("configurable['algocraft'] client required")
    return client


async def research(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    client = _client(config)
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

    return {
        "strategy_candidates": list(strategies),
        "router_candidates": list(routers),
        "research_notes": " | ".join(notes_parts),
        "tickers": tickers,
    }
