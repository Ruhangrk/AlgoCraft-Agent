"""Health check — pings AlgoCraft C++."""

from __future__ import annotations

import httpx
from fastapi import APIRouter

from app.config import get_settings
from app.models.api import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    settings = get_settings()
    url = f"{settings.algocraft_api_url.rstrip('/')}/strategies"
    try:
        async with httpx.AsyncClient(timeout=settings.agent_http_timeout_sec) as client:
            resp = await client.get(url)
        reachable = resp.status_code < 500
        detail = None if reachable else f"status={resp.status_code}"
        return HealthResponse(
            status="ok" if reachable else "degraded",
            cpp_reachable=reachable,
            detail=detail,
        )
    except httpx.HTTPError as exc:
        return HealthResponse(status="degraded", cpp_reachable=False, detail=str(exc))
