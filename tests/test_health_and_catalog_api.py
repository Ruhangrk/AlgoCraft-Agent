"""HTTP smoke for Part 1 endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_llm_catalog_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # No keys → discovery skips live HTTP (status=no_key).
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    resp = client.get("/v1/llm/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_provider"] == "groq"
    assert data["default_temperature"] == 0.2
    assert data["temperature_min"] == 0.0
    assert data["temperature_max"] == 2.0
    ids = {p["id"] for p in data["providers"]}
    assert ids == {"deepseek", "gemini", "openrouter", "groq"}
    for p in data["providers"]:
        assert p["status"] == "no_key"
        assert p["available"] is False
        assert all(m.get("reachable") is False for m in p["models"])
    assert "api_key" not in resp.text.lower()
    assert "env_key" not in resp.text


def test_healthz_endpoint(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "cpp_reachable" in data
    assert isinstance(data["cpp_reachable"], bool)
