"""Mocked httpx tests for AlgocraftClient."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.tools.algocraft_client import AlgocraftApiError, AlgocraftClient

BASE = "http://algocraft.test"


@pytest.fixture
async def client() -> AlgocraftClient:
    c = AlgocraftClient(base_url=BASE, jwt="test-jwt")
    yield c
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_login_stores_token(client: AlgocraftClient) -> None:
    respx.post(f"{BASE}/auth/login").mock(
        return_value=httpx.Response(200, json={"token": "abc", "user": {"id": 1}})
    )
    token = await client.login("u", "p")
    assert token == "abc"
    assert client.jwt == "abc"


@pytest.mark.asyncio
@respx.mock
async def test_list_strategies(client: AlgocraftClient) -> None:
    respx.get(f"{BASE}/strategies").mock(
        return_value=httpx.Response(200, json=["hammer_reversal", "ema_crossover"])
    )
    names = await client.list_strategies()
    assert names == ["hammer_reversal", "ema_crossover"]


@pytest.mark.asyncio
@respx.mock
async def test_start_backtest_sends_required_fields(client: AlgocraftClient) -> None:
    route = respx.post(f"{BASE}/workbooks/3/backtests/start").mock(
        return_value=httpx.Response(
            201, json={"id": 9, "fills": 2, "pnl_paise": 100}
        )
    )
    row = await client.start_backtest(
        3,
        ticker="ONGC",
        strategy="hammer_reversal",
        from_ns=1,
        to_ns=2,
        capital_paise=100_000_00,
    )
    assert row["id"] == 9
    assert route.called
    sent = json.loads(route.calls.last.request.content.decode())
    assert sent["ticker"] == "ONGC"
    assert sent["strategy"] == "hammer_reversal"
    assert sent["from_ns"] == 1
    assert sent["to_ns"] == 2
    assert "Authorization" in route.calls.last.request.headers
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-jwt"


@pytest.mark.asyncio
@respx.mock
async def test_api_error_on_4xx(client: AlgocraftClient) -> None:
    respx.get(f"{BASE}/strategies").mock(
        return_value=httpx.Response(401, json={"error": "missing token"})
    )
    with pytest.raises(AlgocraftApiError) as ei:
        await client.list_strategies()
    assert ei.value.status == 401
    assert ei.value.body == {"error": "missing token"}


@pytest.mark.asyncio
@respx.mock
async def test_with_jwt_does_not_mutate_original(client: AlgocraftClient) -> None:
    other = client.with_jwt("other-token")
    assert client.jwt == "test-jwt"
    assert other.jwt == "other-token"
    await other.aclose()


def test_validate_strategy_name() -> None:
    assert AlgocraftClient.validate_strategy_name("my_mean_revert") == "my_mean_revert"
    with pytest.raises(ValueError):
        AlgocraftClient.validate_strategy_name("Bad-Name")
