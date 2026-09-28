"""Execute node — ensure market data, then backtest or hist run on C++."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState
from app.tools.timeutil import ns_to_ist_ymd


def _client(config: RunnableConfig) -> Any:
    conf = (config or {}).get("configurable") or {}
    client = conf.get("algocraft")
    if client is None:
        raise RuntimeError("configurable['algocraft'] client required")
    return client


async def _ensure_bars(client: Any, chosen: dict[str, Any]) -> str | None:
    """Best-effort ensure 1m bars for backtest window. Returns error string or None."""
    ticker = chosen.get("ticker")
    if not ticker:
        return None
    from_ymd = chosen.get("session_from") or ns_to_ist_ymd(int(chosen["from_ns"]))
    to_ymd = chosen.get("session_to") or ns_to_ist_ymd(int(chosen["to_ns"]))
    if not hasattr(client, "ensure_market_data"):
        return None
    try:
        raw = await client.ensure_market_data(
            {"tickers": [str(ticker)], "from": from_ymd, "to": to_ymd}
        )
        results = (raw or {}).get("results") or []
        for row in results:
            if isinstance(row, dict) and row.get("ticker") == ticker and not row.get("ok", True):
                return f"ensure_market_data failed for {ticker}: {row.get('error')}"
        return None
    except Exception as exc:  # noqa: BLE001
        return f"ensure_market_data failed: {exc}"


async def execute(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    client = _client(config)
    intent = state.get("intent") or "unknown"
    chosen = dict(state.get("chosen") or {})
    wid = state.get("workbook_id")

    if not wid:
        try:
            wid = await client.create_workbook(
                "agent-session", int(chosen.get("capital_paise", 1_00_000_00))
            )
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
            # Normalize hist metrics for evaluate (engine uses returned_paise).
            if "pnl_paise" not in raw and "returned_paise" in raw:
                raw = {**raw, "pnl_paise": int(raw.get("returned_paise") or 0)}
            rid = int(raw.get("run_id") or 0)
            events: list[Any] = []
            if rid and hasattr(client, "run_events"):
                try:
                    events = await client.run_events(int(wid), rid, include="routing,fill")
                except Exception as exc:  # noqa: BLE001
                    raw = {**raw, "events_error": str(exc)}
            raw = {
                **raw,
                "events": events,
                "event_count": len(events),
            }
            return {"cpp_results": raw, "workbook_id": int(wid), "error": None}

        ensure_err = await _ensure_bars(client, chosen)
        raw = await client.start_backtest(
            int(wid),
            ticker=str(chosen["ticker"]),
            strategy=str(chosen["strategy"]),
            from_ns=int(chosen["from_ns"]),
            to_ns=int(chosen["to_ns"]),
            capital_paise=int(chosen["capital_paise"]),
        )
        if ensure_err and int(raw.get("fills") or 0) == 0:
            return {
                "cpp_results": raw,
                "workbook_id": int(wid),
                "error": ensure_err,
            }
        return {"cpp_results": raw, "workbook_id": int(wid), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"execute failed: {exc}",
            "cpp_results": {},
            "workbook_id": int(wid) if wid else None,
        }
