"""Live LLM model discovery: YAML allowlist ∩ provider list-models."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.llm.catalog import LlmCatalog, ProviderSpec, load_catalog

_DEFAULT_TTL_SEC = 600.0  # 10 minutes
_OPENAI_COMPAT = frozenset({"deepseek", "openrouter", "groq"})


@dataclass
class ProviderDiscovery:
    id: str
    label: str
    available: bool
    status: str  # ok | no_key | unreachable | rate_limited
    models: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _CacheEntry:
    expires_at: float
    providers: list[ProviderDiscovery]


_cache: _CacheEntry | None = None
_rate_limited_until: dict[str, float] = {}


def clear_discovery_cache() -> None:
    global _cache
    _cache = None
    _rate_limited_until.clear()


def mark_provider_rate_limited(provider: str, ttl_sec: float = _DEFAULT_TTL_SEC) -> None:
    _rate_limited_until[provider] = time.monotonic() + ttl_sec
    # Invalidate catalog cache so next GET reflects status.
    global _cache
    _cache = None


def _normalize_model_id(provider: str, model_id: str) -> str:
    mid = model_id.strip()
    if provider == "gemini" and mid.startswith("models/"):
        mid = mid[len("models/") :]
    return mid


async def _list_openai_compat_models(
    *,
    base_url: str,
    api_key: str,
    timeout: float = 20.0,
) -> tuple[set[str] | None, str | None]:
    """Returns (ids, error_kind) where error_kind is rate_limited|unreachable|None."""
    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
        if resp.status_code == 429:
            return None, "rate_limited"
        if resp.status_code >= 400:
            return None, "unreachable"
        data = resp.json()
        rows = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            return None, "unreachable"
        ids: set[str] = set()
        for row in rows:
            if isinstance(row, dict) and row.get("id"):
                ids.add(str(row["id"]))
            elif isinstance(row, str):
                ids.add(row)
        return ids, None
    except httpx.HTTPError:
        return None, "unreachable"


async def _list_gemini_models(*, api_key: str, timeout: float = 20.0) -> tuple[set[str] | None, str | None]:
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params={"key": api_key})
        if resp.status_code == 429:
            return None, "rate_limited"
        if resp.status_code >= 400:
            return None, "unreachable"
        data = resp.json()
        rows = data.get("models", []) if isinstance(data, dict) else []
        ids: set[str] = set()
        for row in rows:
            if isinstance(row, dict) and row.get("name"):
                ids.add(_normalize_model_id("gemini", str(row["name"])))
        return ids, None
    except httpx.HTTPError:
        return None, "unreachable"


async def _discover_provider(spec: ProviderSpec) -> ProviderDiscovery:
    now = time.monotonic()
    if _rate_limited_until.get(spec.id, 0) > now:
        return ProviderDiscovery(
            id=spec.id,
            label=spec.label,
            available=True,
            status="rate_limited",
            models=[
                {"id": m.id, "label": m.label, "reachable": False} for m in spec.models
            ],
        )

    if not spec.available:
        return ProviderDiscovery(
            id=spec.id,
            label=spec.label,
            available=False,
            status="no_key",
            models=[
                {"id": m.id, "label": m.label, "reachable": False} for m in spec.models
            ],
        )

    api_key = os.environ.get(spec.env_key, "").strip()
    live_ids: set[str] | None
    err: str | None

    if spec.id in _OPENAI_COMPAT:
        if not spec.base_url:
            live_ids, err = None, "unreachable"
        else:
            live_ids, err = await _list_openai_compat_models(
                base_url=spec.base_url, api_key=api_key
            )
    elif spec.id == "gemini":
        live_ids, err = await _list_gemini_models(api_key=api_key)
    else:
        live_ids, err = None, "unreachable"

    if err == "rate_limited":
        mark_provider_rate_limited(spec.id)
        return ProviderDiscovery(
            id=spec.id,
            label=spec.label,
            available=True,
            status="rate_limited",
            models=[
                {"id": m.id, "label": m.label, "reachable": False} for m in spec.models
            ],
        )

    if err == "unreachable" or live_ids is None:
        return ProviderDiscovery(
            id=spec.id,
            label=spec.label,
            available=True,
            status="unreachable",
            models=[
                {"id": m.id, "label": m.label, "reachable": False} for m in spec.models
            ],
        )

    models = []
    for m in spec.models:
        mid = _normalize_model_id(spec.id, m.id)
        reachable = mid in live_ids or m.id in live_ids
        models.append({"id": m.id, "label": m.label, "reachable": reachable})

    return ProviderDiscovery(
        id=spec.id,
        label=spec.label,
        available=True,
        status="ok",
        models=models,
    )


async def discover_catalog(
    *,
    catalog: LlmCatalog | None = None,
    ttl_sec: float = _DEFAULT_TTL_SEC,
    force: bool = False,
) -> dict[str, Any]:
    """Build UI catalog payload with live reachability (TTL-cached)."""
    global _cache
    now = time.monotonic()
    if not force and _cache is not None and _cache.expires_at > now:
        providers = _cache.providers
    else:
        cat = catalog or load_catalog()
        discovered: list[ProviderDiscovery] = []
        for spec in cat.providers.values():
            discovered.append(await _discover_provider(spec))
        _cache = _CacheEntry(expires_at=now + ttl_sec, providers=discovered)
        providers = discovered

    cat = catalog or load_catalog()
    return {
        "default_provider": cat.default_provider,
        "default_model": cat.default_model,
        "default_temperature": cat.default_temperature,
        "temperature_min": cat.temperature_min,
        "temperature_max": cat.temperature_max,
        "providers": [
            {
                "id": p.id,
                "label": p.label,
                "available": p.available,
                "status": p.status,
                "models": p.models,
            }
            for p in providers
        ],
    }
