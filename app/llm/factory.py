"""LLM factory — the only provider switch point."""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.llm.catalog import load_catalog

_OPENAI_COMPAT = frozenset({"deepseek", "openrouter", "groq"})

# Reasoning models (e.g. groq openai/gpt-oss-*) burn completion budget on
# reasoning tokens; too-low max → empty content (finish_reason=length).
# Groq free tier also counts max_tokens against TPM (~8k), so stay ≤4k.
_DEFAULT_MAX_TOKENS = 4096


class LlmConfigError(RuntimeError):
    """Missing key or unsupported provider."""


def _temp_key(temperature: float) -> float:
    """Round so lru_cache keys stay stable for near-identical slider values."""
    return round(float(temperature), 2)


@lru_cache(maxsize=64)
def _build_chat_model(provider: str, model: str, temperature: float) -> BaseChatModel:
    catalog = load_catalog()
    spec = catalog.resolve(provider, model)

    api_key = os.environ.get(spec.env_key, "").strip()
    if not api_key:
        raise LlmConfigError(f"{spec.env_key} not set (provider={provider})")

    if provider in _OPENAI_COMPAT:
        if not spec.base_url:
            raise LlmConfigError(f"provider {provider} requires base_url in catalog")
        kwargs: dict = {
            "model": model,
            "api_key": api_key,
            "base_url": spec.base_url,
            "temperature": temperature,
            "max_tokens": _DEFAULT_MAX_TOKENS,
        }
        # gpt-oss reasoning can consume the entire completion budget → empty
        # content. Prefer low effort for agent tool/JSON turns.
        if provider == "groq" and "gpt-oss" in model:
            kwargs["extra_body"] = {"reasoning_effort": "low"}
        return ChatOpenAI(**kwargs)

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=_DEFAULT_MAX_TOKENS,
        )

    raise LlmConfigError(f"unsupported provider: {provider}")


def get_chat_model(
    provider: str,
    model: str,
    temperature: float | None = None,
) -> BaseChatModel:
    """Build (and cache) a chat model for allowlisted provider/model + temperature."""
    catalog = load_catalog()
    if temperature is None:
        temperature = catalog.default_temperature
    temp = _temp_key(catalog.clamp_temperature(temperature))
    return _build_chat_model(provider, model, temp)


def clear_model_cache() -> None:
    _build_chat_model.cache_clear()
