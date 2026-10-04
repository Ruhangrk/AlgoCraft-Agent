"""Chat + SSE API tests (mocked graph runner)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.store.sessions import get_session_store


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    get_session_store().clear()
    yield
    get_session_store().clear()


@pytest.fixture
def session_id(client: TestClient) -> str:
    resp = client.post(
        "/v1/sessions",
        json={},
        headers={"Authorization": "Bearer test-jwt"},
    )
    assert resp.status_code == 201
    return resp.json()["session_id"]


@pytest.mark.asyncio
async def test_chat_and_sse_stream(
    client: TestClient, session_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_phase_a(**kwargs):  # noqa: ANN003
        assert kwargs["user_jwt"] == "test-jwt"
        assert "Backtest" in kwargs["message"]
        return {
            "intent": "backtest",
            "eval_verdict": "pass",
            "response_text": "ok backtest",
            "metrics": {"fills": 4, "pnl_paise": 10},
            "card": {"verdict": "pass", "intent": "backtest"},
            "chosen": {"strategy": "hammer_reversal", "ticker": "RELIANCE"},
            "cpp_results": {"id": 1, "fills": 4},
            "workbook_id": 7,
            "error": None,
            "thinking": [
                {
                    "agent": "classify_intent",
                    "phase": "decide",
                    "thought": "intent=backtest",
                }
            ],
        }

    monkeypatch.setattr("app.api.chat.run_phase_a", fake_run_phase_a)

    chat = client.post(
        "/v1/chat",
        json={"session_id": session_id, "message": "Backtest hammer_reversal on RELIANCE"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["verdict"] == "pass"
    assert body["card"]["verdict"] == "pass"
    assert body["metrics"]["fills"] == 4
    assert body["thinking"]
    assert body["thinking"][0]["agent"] == "classify_intent"

    detail = client.get(f"/v1/sessions/{session_id}").json()
    assert len(detail["messages"]) == 2
    assert detail["last_card"]["verdict"] == "pass"
    assert detail["workbook_id"] == 7
    assert detail["last_thinking"]

    # SSE replay
    with client.stream("GET", f"/v1/chat/{session_id}/stream") as stream:
        assert stream.status_code == 200
        raw = "".join(stream.iter_text())
    assert "event: thinking" in raw or "thinking" in raw
    assert "done" in raw


def test_chat_missing_session(client: TestClient) -> None:
    resp = client.post("/v1/chat", json={"session_id": "nope", "message": "hi"})
    assert resp.status_code == 404


def test_stream_before_chat(client: TestClient, session_id: str) -> None:
    with client.stream("GET", f"/v1/chat/{session_id}/stream") as stream:
        raw = "".join(stream.iter_text())
    assert "no_events" in raw or "No chat turn" in raw
