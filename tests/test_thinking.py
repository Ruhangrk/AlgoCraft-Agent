"""Router-first graph: chat/clarify skip execute; create interviews; backtest explicit."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from app.graph.graph import build_graph, reset_graph_cache


@pytest.fixture(autouse=True)
def _reset_graph() -> None:
    reset_graph_cache()
    yield
    reset_graph_cache()


class FakeClient:
    async def list_strategies(self) -> list[str]:
        return ["hammer_reversal", "ema_crossover", "two_consecutive_bars"]

    async def list_routers(self) -> list[str]:
        return ["default_router"]

    async def search_instruments(self, q: str, limit: int = 20) -> list[dict]:
        return [{"ticker": q}]

    async def create_workbook(self, name: str, capital_paise: int) -> int:
        raise AssertionError("should not create workbook for chat/clarify")

    async def start_backtest(self, wid: int, **kw):  # noqa: ANN003
        raise AssertionError("should not backtest unless explicit")


@pytest.mark.asyncio
async def test_hi_routes_to_chat_no_research_execute() -> None:
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="hi")],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": FakeClient(), "llm": None}},
    )
    assert result["intent"] == "chat"
    agents = [t["agent"] for t in (result.get("thinking") or [])]
    assert "route" in agents
    assert "respond" in agents
    assert "execute" not in agents
    assert "research" not in agents
    assert "backtest" not in result["response_text"].lower() or "Backtest `" not in result[
        "response_text"
    ]


@pytest.mark.asyncio
async def test_ambiguous_hi_message_clarifies() -> None:
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="I just said you HI ?")],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": FakeClient(), "llm": None}},
    )
    assert result["intent"] == "clarify"
    assert "execute" not in [t["agent"] for t in (result.get("thinking") or [])]


@pytest.mark.asyncio
async def test_create_interview_asks_for_ticker() -> None:
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content="create a strategy that buys after two red bars")
            ],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": FakeClient(), "llm": None}},
    )
    assert result["intent"] == "create"
    assert result.get("create_ready") is False
    assert "ticker" in (result.get("create_draft") or {}).get("missing", [])
    assert "ticker" in result["response_text"].lower()


@pytest.mark.asyncio
async def test_discuss_lists_strategies() -> None:
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="explain what strategies we have")],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": FakeClient(), "llm": None}},
    )
    assert result["intent"] == "discuss"
    assert "hammer_reversal" in result["response_text"]
    assert "execute" not in [t["agent"] for t in (result.get("thinking") or [])]


@pytest.mark.asyncio
async def test_discuss_focuses_named_strategy() -> None:
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="two_consecutive_bars lets discuss this")],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": FakeClient(), "llm": None}},
    )
    assert result["intent"] == "discuss"
    assert result.get("topic_strategy") == "two_consecutive_bars"
    assert "Let's talk about" in result["response_text"]
    assert "**Idea:**" in result["response_text"] or "Idea:" in result["response_text"]
    assert "Happy to discuss. The engine currently exposes" not in result["response_text"]


@pytest.mark.asyncio
async def test_backtest_typo_and_mm_ticker() -> None:
    class BtClient(FakeClient):
        async def create_workbook(self, name: str, capital_paise: int) -> int:
            return 1

        async def ensure_market_data(self, body: dict) -> dict:
            return {"results": [{"ticker": body["tickers"][0], "ok": True}]}

        async def start_backtest(self, wid: int, **kw):  # noqa: ANN003
            self.last = kw
            return {"id": 1, "fills": 3, "pnl_paise": 10}

    client = BtClient()
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="backest M&M for 28th sept 26, with strategy hammer_reversal"
                )
            ],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": client, "llm": None}},
    )
    assert result["intent"] == "backtest"
    assert result["chosen"]["strategy"] == "hammer_reversal"
    assert result["chosen"]["ticker"] == "M&M"
    assert result["chosen"]["session_from"] == "2026-09-28"
    assert result["eval_verdict"] == "pass"
