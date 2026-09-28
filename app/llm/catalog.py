"""LLM catalog: load allowlisted providers/models from YAML."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.config import get_settings


class ModelSpec(BaseModel):
    id: str
    label: str


class ProviderSpec(BaseModel):
    id: str
    label: str
    env_key: str
    base_url: str | None = None
    models: list[ModelSpec] = Field(default_factory=list)

    def has_model(self, model_id: str) -> bool:
        return any(m.id == model_id for m in self.models)

    @property
    def available(self) -> bool:
        key = os.environ.get(self.env_key, "")
        return bool(key and key.strip())


class LlmCatalog(BaseModel):
    default_provider: str
    default_model: str
    default_temperature: float = 0.2
    temperature_min: float = 0.0
    temperature_max: float = 2.0
    providers: dict[str, ProviderSpec]

    def resolve(self, provider: str, model: str) -> ProviderSpec:
        p = self.providers.get(provider)
        if p is None or not p.has_model(model):
            raise ValueError(f"model not allowed: {provider}/{model}")
        return p

    def clamp_temperature(self, temperature: float) -> float:
        t = float(temperature)
        if t < self.temperature_min or t > self.temperature_max:
            raise ValueError(
                f"temperature {t} out of range "
                f"[{self.temperature_min}, {self.temperature_max}]"
            )
        return t

    def defaults(self) -> tuple[str, str, float]:
        settings = get_settings()
        provider = settings.agent_default_llm_provider or self.default_provider
        model = settings.agent_default_llm_model or self.default_model
        self.resolve(provider, model)
        return provider, model, self.default_temperature

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "default_temperature": self.default_temperature,
            "temperature_min": self.temperature_min,
            "temperature_max": self.temperature_max,
            "providers": [
                {
                    "id": p.id,
                    "label": p.label,
                    "available": p.available,
                    "models": [{"id": m.id, "label": m.label} for m in p.models],
                }
                for p in self.providers.values()
            ],
        }


class LlmCatalogError(ValueError):
    """Invalid or missing LLM catalog."""


def _parse_catalog(raw: dict[str, Any]) -> LlmCatalog:
    if not isinstance(raw, dict):
        raise LlmCatalogError("llm catalog must be a mapping")
    providers_raw = raw.get("providers") or {}
    providers: dict[str, ProviderSpec] = {}
    for pid, pdata in providers_raw.items():
        if not isinstance(pdata, dict):
            raise LlmCatalogError(f"provider {pid!r} must be a mapping")
        providers[pid] = ProviderSpec(id=pid, **pdata)
    catalog = LlmCatalog(
        default_provider=raw["default_provider"],
        default_model=raw["default_model"],
        default_temperature=float(raw.get("default_temperature", 0.2)),
        temperature_min=float(raw.get("temperature_min", 0.0)),
        temperature_max=float(raw.get("temperature_max", 2.0)),
        providers=providers,
    )
    # Ensure defaults themselves are allowlisted
    catalog.resolve(catalog.default_provider, catalog.default_model)
    return catalog


@lru_cache
def load_catalog(path: str | None = None) -> LlmCatalog:
    catalog_path = Path(path) if path else get_settings().llm_catalog_path
    if not catalog_path.is_file():
        raise LlmCatalogError(f"llm catalog not found: {catalog_path}")
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    return _parse_catalog(raw)


def clear_catalog_cache() -> None:
    load_catalog.cache_clear()
