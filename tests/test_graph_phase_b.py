"""Phase B create path with mocked compile (interview → design → compile)."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.graph import build_graph, reset_graph_cache
from app.tools.algocraft_client import AlgocraftApiError


@pytest.fixture(autouse=True)
def _reset_graph() -> None:
    reset_graph_cache()
    yield
    reset_graph_cache()


class FakeCompileClient:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.compiles: list[dict] = []

    async def list_strategies(self) -> list[str]:
        return ["hammer_reversal"]

    async def list_routers(self) -> list[str]:
        return ["default_router"]

    async def agent_compile(
        self,
        name: str,
        hpp: str,
        cpp: str,
        class_name: str = "",
        *,
        kind: str = "strategy",
    ) -> dict:
        self.compiles.append(
            {"name": name, "hpp": hpp, "cpp": cpp, "class_name": class_name, "kind": kind}
        )
        if len(self.compiles) <= self.fail_times:
            raise AlgocraftApiError(
                422,
                {
                    "ok": False,
                    "name": name,
                    "class_name": class_name,
                    "log": "error: expected ';' before '}'",
                    "sandbox_dir": f"/tmp/{name}",
                },
            )
        return {
            "ok": True,
            "name": name,
            "class_name": class_name,
            "sandbox_dir": f"/tmp/{name}",
            "log": "ok",
        }


_CREATE_MSG = (
    "create a strategy on RELIANCE named agent_smoke_churn that buys one share "
    "every minute before 15:15 and flattens after"
)


@pytest.mark.asyncio
async def test_phase_b_create_compiles_need_human() -> None:
    graph = build_graph()
    client = FakeCompileClient()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=_CREATE_MSG)],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": client, "llm": None}},
    )
    assert result["intent"] == "create"
    assert result["chosen"]["name"] == "agent_smoke_churn"
    assert result["eval_verdict"] == "need_human"
    assert result["pending_human"] == "promote"
    assert client.compiles
    assert "Compiled strategy" in result["response_text"]


@pytest.mark.asyncio
async def test_phase_b_compile_fail_without_llm() -> None:
    graph = build_graph()
    client = FakeCompileClient(fail_times=99)
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "create a strategy on TCS named bad_strat that fades the open dump"
                    )
                )
            ],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": client, "llm": None}},
    )
    assert result["intent"] == "create"
    assert result["eval_verdict"] == "error"
    assert result["compile_attempts"] == 1


@pytest.mark.asyncio
async def test_phase_b_llm_fix_retries_then_ok() -> None:
    class FakeFixLlm:
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, messages):  # noqa: ANN001
            self.calls += 1
            text = " ".join(str(getattr(m, "content", m)) for m in messages)
            if "Fix the strategy" in text or "Compiler log" in text:
                payload = {
                    "hpp": "#pragma once\n#include \"algocraft/strategies/strategy.hpp\"\n",
                    "cpp": '// fixed\n#include "algocraft/strategies/my_mean_revert.hpp"\n',
                }
                return AIMessage(content=json.dumps(payload))
            payload = {
                "name": "my_mean_revert",
                "class_name": "MyMeanRevert",
                "kind": "strategy",
                "hpp": "#pragma once\n",
                "cpp": "#include \"algocraft/strategies/my_mean_revert.hpp\"\n",
            }
            return AIMessage(content=json.dumps(payload))

    graph = build_graph()
    client = FakeCompileClient(fail_times=1)
    llm = FakeFixLlm()
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "write a strategy named my_mean_revert on INFY that mean-reverts "
                        "to VWAP after a 50bps dump"
                    )
                )
            ],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": client, "llm": llm}},
    )
    assert result["eval_verdict"] == "need_human"
    assert result["compile_attempts"] == 2
    assert len(client.compiles) == 2
    assert result["chosen"]["name"] == "my_mean_revert"


@pytest.mark.asyncio
async def test_phase_a_still_routes_to_propose() -> None:
    class FakeClient:
        async def list_strategies(self) -> list[str]:
            return ["hammer_reversal"]

        async def list_routers(self) -> list[str]:
            return ["default_router"]

        async def create_workbook(self, name: str, capital_paise: int) -> int:
            return 1

        async def ensure_market_data(self, body: dict) -> dict:
            return {"results": [{"ticker": "RELIANCE", "ok": True}]}

        async def start_backtest(self, wid: int, **kw):  # noqa: ANN003
            return {"id": 1, "fills": 3, "pnl_paise": 10}

    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Backtest hammer_reversal on RELIANCE")],
            "iteration": 0,
            "max_iterations": 1,
            "create_draft": {},
        },
        config={"configurable": {"algocraft": FakeClient(), "llm": None}},
    )
    assert result["intent"] == "backtest"
    assert result["eval_verdict"] == "pass"
    assert "strategy" in result["chosen"]
