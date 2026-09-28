"""Map provider SDK / HTTP errors → structured UI errors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.llm.discover import mark_provider_rate_limited

_RATE_HINTS = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "quota",
    "resource exhausted",
    "resource_exhausted",
    "too many requests",
    "tpm",
    "rpm",
)


@dataclass(frozen=True)
class LlmStructuredError:
    code: str
    provider: str
    model: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "http_status", "code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    resp = getattr(exc, "response", None)
    if resp is not None:
        sc = getattr(resp, "status_code", None)
        if isinstance(sc, int):
            return sc
    return None


def is_rate_limit_error(exc: BaseException) -> bool:
    sc = _status_code(exc)
    if sc == 429:
        return True
    name = type(exc).__name__.lower()
    if "ratelimit" in name or "quota" in name:
        return True
    text = str(exc).lower()
    return any(h in text for h in _RATE_HINTS)


def classify_llm_error(
    exc: BaseException,
    *,
    provider: str,
    model: str,
) -> LlmStructuredError | None:
    """
    If `exc` is a rate/quota limit, return structured error for SSE/JSON.
    Otherwise return None (caller handles generic failures).
    """
    if not is_rate_limit_error(exc):
        return None
    mark_provider_rate_limited(provider)
    return LlmStructuredError(
        code="llm_rate_limited",
        provider=provider,
        model=model,
        message=(
            f"Provider '{provider}' (model '{model}') hit its rate/quota limit. "
            "Switch provider or model in the dropdowns and try again."
        ),
    )
