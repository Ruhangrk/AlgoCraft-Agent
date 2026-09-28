"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    cpp_reachable: bool
    detail: str | None = None


class LlmModelOut(BaseModel):
    id: str
    label: str
    reachable: bool | None = None


class LlmProviderOut(BaseModel):
    id: str
    label: str
    available: bool
    status: str | None = None
    models: list[LlmModelOut] = Field(default_factory=list)


class LlmCatalogResponse(BaseModel):
    default_provider: str
    default_model: str
    default_temperature: float = 0.2
    temperature_min: float = 0.0
    temperature_max: float = 2.0
    providers: list[LlmProviderOut]


class CreateSessionRequest(BaseModel):
    workbook_id: int | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None


class PatchLlmRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None


class SessionLlmOut(BaseModel):
    session_id: str
    provider: str
    model: str
    temperature: float
    workbook_id: int | None = None


class SessionDetailOut(BaseModel):
    session_id: str
    provider: str
    model: str
    temperature: float
    workbook_id: int | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    last_metrics: dict[str, Any] | None = None
    last_card: dict[str, Any] | None = None
    pending_human: Literal["none", "promote", "activate"] = "none"
    pending_strategy_name: str | None = None
