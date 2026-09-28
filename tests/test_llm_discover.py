"""Tests for live discovery ∩ YAML and rate-limit mapping."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.llm.catalog import clear_catalog_cache, load_catalog
from app.llm.discover import clear_discovery_cache, discover_catalog, mark_provider_rate_limited
from app.llm.errors import classify_llm_error, is_rate_limit_error


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_catalog_cache()
    clear_discovery_cache()
    yield
    clear_catalog_cache()
    clear_discovery_cache()


@pytest.mark.asyncio
@respx.mock
async def test_discover_intersects_openai_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    respx.get("https://api.groq.com/openai/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "openai/gpt-oss-20b"},
                    {"id": "other-model"},
                ]
            },
        )
    )

    data = await discover_catalog(force=True)
    groq = next(p for p in data["providers"] if p["id"] == "groq")
    assert groq["available"] is True
    assert groq["status"] == "ok"
    by_id = {m["id"]: m["reachable"] for m in groq["models"]}
    assert by_id["openai/gpt-oss-20b"] is True
    assert by_id["openai/gpt-oss-120b"] is False

    gemini = next(p for p in data["providers"] if p["id"] == "gemini")
    assert gemini["status"] == "no_key"


@pytest.mark.asyncio
@respx.mock
async def test_discover_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    respx.get("https://api.groq.com/openai/v1/models").mock(
        return_value=httpx.Response(429, json={"error": "rate"})
    )
    data = await discover_catalog(force=True)
    groq = next(p for p in data["providers"] if p["id"] == "groq")
    assert groq["status"] == "rate_limited"


def test_classify_rate_limit() -> None:
    class FakeRateLimit(Exception):
        status_code = 429

    err = classify_llm_error(FakeRateLimit("too many"), provider="groq", model="x")
    assert err is not None
    assert err.code == "llm_rate_limited"
    assert "Switch provider or model" in err.message
    assert is_rate_limit_error(FakeRateLimit("x"))


def test_classify_non_rate_limit() -> None:
    assert classify_llm_error(RuntimeError("boom"), provider="groq", model="x") is None


@pytest.mark.asyncio
async def test_mark_rate_limited_affects_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    mark_provider_rate_limited("groq", ttl_sec=60)
    data = await discover_catalog(force=True)
    groq = next(p for p in data["providers"] if p["id"] == "groq")
    assert groq["status"] == "rate_limited"


def test_catalog_still_resolves_yaml_allowlist() -> None:
    # Chat path still uses YAML allowlist even if discover marks unreachable.
    cat = load_catalog()
    cat.resolve("groq", "openai/gpt-oss-20b")
