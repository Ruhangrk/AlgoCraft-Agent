"""Session API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.store.sessions import get_session_store


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    get_session_store().clear()
    yield
    get_session_store().clear()


def test_create_session_requires_auth(client: TestClient) -> None:
    resp = client.post("/v1/sessions", json={})
    assert resp.status_code == 401


def test_create_session_defaults(client: TestClient) -> None:
    resp = client.post(
        "/v1/sessions",
        json={},
        headers={"Authorization": "Bearer user-jwt-1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "groq"
    assert data["model"] == "openai/gpt-oss-20b"
    assert data["temperature"] == 0.2
    assert data["session_id"]
    assert "user_jwt" not in data
    assert "jwt" not in data


def test_create_session_custom_llm(client: TestClient) -> None:
    resp = client.post(
        "/v1/sessions",
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "temperature": 0.5,
            "workbook_id": 42,
        },
        headers={"Authorization": "Bearer user-jwt-2"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "deepseek"
    assert data["model"] == "deepseek-chat"
    assert data["temperature"] == 0.5
    assert data["workbook_id"] == 42


def test_create_rejects_bad_pair(client: TestClient) -> None:
    resp = client.post(
        "/v1/sessions",
        json={"provider": "groq", "model": "nope"},
        headers={"Authorization": "Bearer x"},
    )
    assert resp.status_code == 422


def test_get_and_patch_llm(client: TestClient) -> None:
    created = client.post(
        "/v1/sessions",
        json={},
        headers={"Authorization": "Bearer user-jwt-3"},
    ).json()
    sid = created["session_id"]

    got = client.get(f"/v1/sessions/{sid}")
    assert got.status_code == 200
    body = got.json()
    assert body["session_id"] == sid
    assert body["messages"] == []
    assert "user_jwt" not in body

    patched = client.patch(
        f"/v1/sessions/{sid}/llm",
        json={"provider": "openrouter", "model": "deepseek/deepseek-chat", "temperature": 0.8},
    )
    assert patched.status_code == 200
    assert patched.json()["provider"] == "openrouter"
    assert patched.json()["model"] == "deepseek/deepseek-chat"
    assert patched.json()["temperature"] == 0.8

    again = client.get(f"/v1/sessions/{sid}").json()
    assert again["provider"] == "openrouter"
    assert again["temperature"] == 0.8


def test_get_missing_session(client: TestClient) -> None:
    assert client.get("/v1/sessions/does-not-exist").status_code == 404
