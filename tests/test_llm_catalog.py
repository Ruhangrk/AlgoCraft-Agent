"""Tests for LLM catalog allowlist."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.llm.catalog import LlmCatalogError, clear_catalog_cache, load_catalog


def test_load_default_catalog() -> None:
    cat = load_catalog()
    assert cat.default_provider == "groq"
    assert cat.default_model == "openai/gpt-oss-20b"
    assert cat.default_temperature == 0.2
    assert cat.temperature_min == 0.0
    assert cat.temperature_max == 2.0
    assert cat.clamp_temperature(0.5) == 0.5
    with pytest.raises(ValueError, match="temperature"):
        cat.clamp_temperature(-0.1)
    assert "deepseek" in cat.providers
    assert "gemini" in cat.providers
    assert "openrouter" in cat.providers
    assert "groq" in cat.providers
    cat.resolve("deepseek", "deepseek-chat")
    cat.resolve("openrouter", "deepseek/deepseek-chat")


def test_resolve_unknown_raises() -> None:
    cat = load_catalog()
    with pytest.raises(ValueError, match="not allowed"):
        cat.resolve("deepseek", "no-such-model")
    with pytest.raises(ValueError, match="not allowed"):
        cat.resolve("nope", "deepseek-chat")


def test_to_api_dict_hides_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    clear_catalog_cache()
    data = load_catalog().to_api_dict()
    blob = str(data)
    assert "sk-test" not in blob
    assert "env_key" not in blob
    assert "base_url" not in blob
    deepseek = next(p for p in data["providers"] if p["id"] == "deepseek")
    gemini = next(p for p in data["providers"] if p["id"] == "gemini")
    assert deepseek["available"] is True
    assert gemini["available"] is False


def test_missing_catalog_file(tmp_path: Path) -> None:
    clear_catalog_cache()
    with pytest.raises(LlmCatalogError, match="not found"):
        load_catalog(str(tmp_path / "missing.yaml"))
