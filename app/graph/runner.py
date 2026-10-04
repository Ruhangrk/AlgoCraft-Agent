"""Run production graph with a real or injected Algocraft client."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.graph.graph import get_graph
from app.llm.factory import get_chat_model
from app.tools.algocraft_client import AlgocraftClient


async def run_phase_a(
    *,
    message: str,
    user_jwt: str,
    workbook_id: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    client: AlgocraftClient | None = None,
    llm: Any | None = None,
    create_draft: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    One graph turn. Pass session `create_draft` to continue create interviews.
    `llm=None` keeps rules/template path (no quota burn).
    """
    settings = get_settings()
    owns_client = client is None
    if client is None:
        client = AlgocraftClient(base_url=settings.algocraft_api_url, jwt=user_jwt)

    if llm is None and provider and model:
        try:
            llm = get_chat_model(provider, model, temperature)
        except Exception:  # noqa: BLE001 — rules path still works without keys
            llm = None

    graph = get_graph()
    try:
        return await graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "user_jwt": user_jwt,
                "workbook_id": workbook_id,
                "session_id": session_id or "",
                "llm_provider": provider or "",
                "llm_model": model or "",
                "llm_temperature": float(temperature or 0.2),
                "iteration": 0,
                "max_iterations": settings.agent_max_iterations,
                "compile_attempts": 0,
                "create_draft": dict(create_draft or {}),
            },
            config={"configurable": {"algocraft": client, "llm": llm}},
        )
    finally:
        if owns_client:
            await client.aclose()
