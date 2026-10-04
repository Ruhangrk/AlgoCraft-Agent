"""Execute node — ensure market data, then backtest or hist run on C++."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.nodes._common import get_client
from app.graph.state import AgentState
from app.graph.thinking import thought, thoughts
from app.tools.timeutil import ns_to_ist_ymd


async def _ensure_bars(client: Any, chosen: dict[str, Any]) -> str | None:
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
    client = get_client(config)
    intent = state.get("intent") or "unknown"
    chosen = dict(state.get("chosen") or {})
    wid = state.get("workbook_id")

    if not wid:
        try:
            wid = await client.create_workbook(
                "agent-session", int(chosen.get("capital_paise", 1_00_000_00))
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "error": f"create_workbook failed: {exc}",
                "cpp_results": {},
                **thought(
                    "execute",
                    f"create_workbook failed: {exc}",
                    phase="result",
                ),
            }

    try:
        if intent == "route":
            t_start = thought(
                "execute",
                f"Calling C++ start_run router={chosen.get('router')} "
                f"anchor={chosen.get('anchor_date')} workbook={wid}",
                phase="tool",
                data={"workbook_id": wid, "router": chosen.get("router")},
            )
            raw = await client.start_run(
                int(wid),
                router=str(chosen["router"]),
                capital_paise=int(chosen["capital_paise"]),
                anchor_date=str(chosen["anchor_date"]),
            )
            if "pnl_paise" not in raw and "returned_paise" in raw:
                raw = {**raw, "pnl_paise": int(raw.get("returned_paise") or 0)}
            rid = int(raw.get("run_id") or 0)
            events: list[Any] = []
            if rid and hasattr(client, "run_events"):
                try:
                    events = await client.run_events(int(wid), rid, include="routing,fill")
                except Exception as exc:  # noqa: BLE001
                    raw = {**raw, "events_error": str(exc)}
            raw = {**raw, "events": events, "event_count": len(events)}
            return {
                "cpp_results": raw,
                "workbook_id": int(wid),
                "error": None,
                **thoughts(
                    t_start,
                    thought(
                        "execute",
                        f"Hist run done: run_id={rid}, fills={raw.get('fills')}, "
                        f"pnl_paise={raw.get('pnl_paise')}, events={len(events)}",
                        phase="result",
                        data={"run_id": rid, "fills": raw.get("fills")},
                    ),
                ),
            }

        t_start = thought(
            "execute",
            f"Calling C++ start_backtest strategy={chosen.get('strategy')} "
            f"ticker={chosen.get('ticker')} workbook={wid}",
            phase="tool",
            data={
                "workbook_id": wid,
                "strategy": chosen.get("strategy"),
                "ticker": chosen.get("ticker"),
            },
        )
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
                **thoughts(
                    t_start,
                    thought(
                        "execute",
                        f"Backtest empty fills; market-data issue: {ensure_err}",
                        phase="result",
                    ),
                ),
            }
        return {
            "cpp_results": raw,
            "workbook_id": int(wid),
            "error": None,
            **thoughts(
                t_start,
                thought(
                    "execute",
                    f"Backtest done: id={raw.get('id')}, fills={raw.get('fills')}, "
                    f"pnl_paise={raw.get('pnl_paise')}",
                    phase="result",
                    data={"backtest_id": raw.get("id"), "fills": raw.get("fills")},
                ),
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"execute failed: {exc}",
            "cpp_results": {},
            "workbook_id": int(wid) if wid else None,
            **thought("execute", f"execute failed: {exc}", phase="result"),
        }
