"""LLM catalog endpoint for UI provider/model dropdowns."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.llm.discover import discover_catalog
from app.models.api import LlmCatalogResponse

router = APIRouter(prefix="/v1/llm", tags=["llm"])


@router.get("/catalog", response_model=LlmCatalogResponse)
async def get_llm_catalog(
    refresh: bool = Query(default=False, description="Bypass discovery TTL cache"),
) -> LlmCatalogResponse:
    data = await discover_catalog(force=refresh)
    return LlmCatalogResponse.model_validate(data)
