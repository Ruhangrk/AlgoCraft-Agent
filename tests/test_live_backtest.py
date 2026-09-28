"""Optional live C++ backtest smoke (set AGENT_LIVE_CPP=1)."""

from __future__ import annotations

import os

import pytest
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.graph.graph import build_graph
from app.tools.algocraft_client import AlgocraftClient
from app.tools.timeutil import last_n_session_days, session_range_ns

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENT_LIVE_CPP", "").strip() not in {"1", "true", "yes"},
    reason="Set AGENT_LIVE_CPP=1 to run live C++ integration",
)


@pytest.mark.asyncio
async def test_live_backtest_hammer_short_window() -> None:
    settings = get_settings()
    days = last_n_session_days(2)
    from_ns, to_ns = session_range_ns(days[0], days[-1])

    async with AlgocraftClient(base_url=settings.algocraft_api_url) as client:
        await client.login(settings.algocraft_user, settings.algocraft_pass)
        graph = build_graph()
        # Pre-seed chosen path via natural message; window defaults to 2 days
        result = await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=f"Backtest hammer_reversal on RELIANCE from {days[0]} to {days[-1]}"
                    )
                ],
                "iteration": 0,
                "max_iterations": 1,
            },
            config={"configurable": {"algocraft": client}},
        )

    assert result.get("intent") == "backtest"
    assert result.get("chosen", {}).get("strategy") == "hammer_reversal"
    assert result.get("cpp_results"), result.get("error")
    assert "eval_verdict" in result
    assert "card" in result
    # Soft check: engine returned a row (fills may be 0 on quiet window)
@pytest.mark.asyncio
async def test_live_hist_route_with_events() -> None:
    settings = get_settings()
    async with AlgocraftClient(base_url=settings.algocraft_api_url) as client:
        await client.login(settings.algocraft_user, settings.algocraft_pass)
        graph = build_graph()
        result = await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content="Run hist route using live_run_testing_router"
                    )
                ],
                "iteration": 0,
                "max_iterations": 1,
            },
            config={"configurable": {"algocraft": client}},
        )

    assert result.get("intent") == "route"
    assert result.get("chosen", {}).get("router") == "live_run_testing_router"
    assert result.get("cpp_results"), result.get("error")
    assert "run_id" in (result.get("cpp_results") or {})
    assert "event_count" in (result.get("metrics") or {})
    assert "eval_verdict" in result
