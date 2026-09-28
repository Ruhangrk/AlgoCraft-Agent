"""Factory path selection (mocked SDKs)."""

from __future__ import annotations

import pytest

from app.llm.factory import LlmConfigError, clear_model_cache, get_chat_model


def test_openai_compat_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek")
    created: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):  # noqa: ANN003
            created.update(kwargs)

    monkeypatch.setattr("app.llm.factory.ChatOpenAI", FakeChatOpenAI)
    clear_model_cache()
    model = get_chat_model("deepseek", "deepseek-chat", temperature=0.7)
    assert isinstance(model, FakeChatOpenAI)
    assert created["model"] == "deepseek-chat"
    assert created["base_url"] == "https://api.deepseek.com"
    assert created["api_key"] == "sk-deepseek"
    assert created["temperature"] == 0.7


def test_gemini_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    created: dict = {}

    class FakeGemini:
        def __init__(self, **kwargs):  # noqa: ANN003
            created.update(kwargs)

    monkeypatch.setattr("app.llm.factory.ChatGoogleGenerativeAI", FakeGemini)
    clear_model_cache()
    model = get_chat_model("gemini", "gemini-3.8-flash")
    assert isinstance(model, FakeGemini)
    assert created["model"] == "gemini-3.8-flash"
    assert created["google_api_key"] == "gem-key"
    assert created["temperature"] == 0.2


def test_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    clear_model_cache()
    with pytest.raises(LlmConfigError, match="GROQ_API_KEY"):
        get_chat_model("groq", "openai/gpt-oss-20b")


def test_rejects_unknown_pair() -> None:
    clear_model_cache()
    with pytest.raises(ValueError, match="not allowed"):
        get_chat_model("deepseek", "gpt-4o")


def test_temperature_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    clear_model_cache()
    with pytest.raises(ValueError, match="temperature"):
        get_chat_model("groq", "openai/gpt-oss-20b", temperature=9.0)
