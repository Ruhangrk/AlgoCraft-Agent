"""Execute node — run backtest or hist run on C++."""

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


async def execute(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    client = _client(config)
    intent = state.get("intent") or "unknown"
    chosen = dict(state.get("chosen") or {})
    wid = state.get("workbook_id")

    if not wid:
        # Create a disposable workbook for the agent turn
        try:
            wid = await client.create_workbook("agent-session", chosen.get("capital_paise", 1_00_000_00))
        except Exception as exc:  # noqa: BLE001
            return {"error": f"create_workbook failed: {exc}", "cpp_results": {}}

    try:
        if intent == "route":
            raw = await client.start_run(
                int(wid),
                router=str(chosen["router"]),
                capital_paise=int(chosen["capital_paise"]),
                anchor_date=str(chosen["anchor_date"]),
            )
        else:
            raw = await client.start_backtest(
                int(wid),
                ticker=str(chosen["ticker"]),
                strategy=str(chosen["strategy"]),
                from_ns=int(chosen["from_ns"]),
                to_ns=int(chosen["to_ns"]),
                capital_paise=int(chosen["capital_paise"]),
            )
        return {"cpp_results": raw, "workbook_id": int(wid), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"execute failed: {exc}", "cpp_results": {}, "workbook_id": int(wid)}
