"""Phase A graph with mocked Algocraft client (no live LLM)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from app.graph.graph import build_graph


class FakeClient:
    def __init__(self) -> None:
        self.backtests: list[dict] = []

    async def list_strategies(self) -> list[str]:
        return ["hammer_reversal", "ema_crossover"]

    async def list_routers(self) -> list[str]:
        return ["default_router", "top15_week_router"]

    async def search_instruments(self, q: str, limit: int = 20) -> list[dict]:
        return [{"ticker": q}]

    async def create_workbook(self, name: str, capital_paise: int) -> int:
        return 7

    async def start_backtest(self, wid: int, **kw):  # noqa: ANN003
        self.backtests.append({"wid": wid, **kw})
        return {"id": 99, "fills": 4, "pnl_paise": 250}

    async def start_run(self, wid: int, **kw):  # noqa: ANN003
        return {"run_id": 1, "fills": 3, "pnl_paise": 50, **kw}


@pytest.mark.asyncio
async def test_phase_a_backtest_ends_in_respond_with_metrics() -> None:
    graph = build_graph()
    client = FakeClient()
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="Backtest hammer_reversal on ONGC for last 5 sessions with 1L"
                )
            ],
            "iteration": 0,
            "max_iterations": 3,
        },
        config={"configurable": {"algocraft": client, "llm": None}},
    )

    assert result["intent"] == "backtest"
    assert result["eval_verdict"] == "pass"
    assert result["metrics"]["fills"] == 4
    assert result["metrics"]["pnl_paise"] == 250
    assert result["card"]["verdict"] == "pass"
    assert result["chosen"]["strategy"] == "hammer_reversal"
    assert result["chosen"]["ticker"] == "ONGC"
    assert client.backtests
    assert "response_text" in result


@pytest.mark.asyncio
async def test_phase_a_retry_then_respond_on_weak() -> None:
    class WeakThenPassClient(FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.n = 0

        async def start_backtest(self, wid: int, **kw):  # noqa: ANN003
            self.n += 1
            if self.n == 1:
                return {"id": 1, "fills": 3, "pnl_paise": 0}  # weak
            return {"id": 2, "fills": 3, "pnl_paise": 10}  # pass

    graph = build_graph()
    client = WeakThenPassClient()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Backtest ema_crossover on RELIANCE")],
            "iteration": 0,
            "max_iterations": 3,
        },
        config={"configurable": {"algocraft": client}},
    )
    assert client.n == 2
    assert result["eval_verdict"] == "pass"
    assert result["iteration"] == 1
