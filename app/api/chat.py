"""Chat routes: sync graph turn + SSE replay/stream."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.sessions import _resolve_llm
from app.graph.lifecycle import run_confirm
from app.graph.runner import run_phase_a
from app.llm.errors import classify_llm_error
from app.store.sessions import Session, get_session_store

router = APIRouter(prefix="/v1/chat", tags=["chat"])

_APPROVE = {
    "APPROVE_PROMOTE": "promote",
    "APPROVE_ACTIVATE": "activate",
}


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None


class ChatResponse(BaseModel):
    session_id: str
    intent: str | None = None
    verdict: str | None = None
    response_text: str | None = None
    metrics: dict[str, Any] | None = None
    card: dict[str, Any] | None = None
    provider: str
    model: str
    temperature: float
    error: str | None = None


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, default=str)}


def _apply_result_to_session(session: Session, message: str, result: dict[str, Any]) -> list[dict[str, str]]:
    """Update session history/card and build SSE event list for stream replay."""
    session.messages.append({"role": "user", "content": message})
    text = result.get("response_text") or ""
    if text:
        session.messages.append({"role": "assistant", "content": text})
    session.last_metrics = result.get("metrics")
    session.last_card = result.get("card")
    if result.get("workbook_id") is not None:
        session.workbook_id = int(result["workbook_id"])
    if result.get("pending_human") is not None:
        session.pending_human = str(result["pending_human"])
    name = (result.get("chosen") or {}).get("name") or (
        (result.get("card") or {}).get("strategy_name")
    )
    if session.pending_human in ("promote", "activate") and name:
        session.pending_strategy_name = str(name)
    elif session.pending_human == "none":
        # Keep name through activate confirm; clear only when fully done
        if (result.get("metrics") or {}).get("activated"):
            session.pending_strategy_name = None

    events: list[dict[str, str]] = []
    intent = result.get("intent")
    if intent:
        events.append(_sse("tool", {"node": "classify_intent", "intent": intent}))
    chosen = result.get("chosen") or {}
    if chosen and intent == "codegen_strategy":
        events.append(
            _sse(
                "tool",
                {
                    "node": "design_code",
                    "name": chosen.get("name"),
                    "source": chosen.get("source"),
                },
            )
        )
    elif chosen:
        events.append(
            _sse(
                "tool",
                {
                    "node": "propose",
                    "chosen": {k: v for k, v in chosen.items() if k not in ("hpp", "cpp")},
                },
            )
        )
    if result.get("cpp_results"):
        node = "compile_loop" if intent == "codegen_strategy" else "execute"
        events.append(
            _sse(
                "tool",
                {
                    "node": node,
                    "fills": (result.get("metrics") or {}).get("fills"),
                    "run_id": (result.get("metrics") or {}).get("run_id"),
                    "backtest_id": (result.get("metrics") or {}).get("backtest_id"),
                    "compile_ok": (result.get("metrics") or {}).get("compile_ok"),
                    "compile_attempts": result.get("compile_attempts"),
                },
            )
        )
    if result.get("card"):
        events.append(_sse("card", result["card"]))
    if text:
        events.append(_sse("token", {"text": text}))
    if result.get("error"):
        events.append(_sse("error", {"code": "agent_error", "message": result["error"]}))
    events.append(
        _sse(
            "done",
            {
                "verdict": result.get("eval_verdict"),
                "session_id": session.session_id,
            },
        )
    )
    session.stream_events = events
    get_session_store().update(session)
    return events


@router.post("", response_model=ChatResponse)
async def post_chat(body: ChatRequest) -> ChatResponse:
    store = get_session_store()
    session = store.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    provider, model, temperature = _resolve_llm(
        provider=body.provider,
        model=body.model,
        temperature=body.temperature,
        fallback_provider=session.provider,
        fallback_model=session.model,
        fallback_temperature=session.temperature,
    )
    # Persist overrides for subsequent turns
    session.provider = provider
    session.model = model
    session.temperature = temperature
    store.update(session)

    try:
        approve = _APPROVE.get(body.message.strip().upper())
        if approve:
            if session.pending_human != approve:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "wrong_gate",
                        "message": (
                            f"session pending_human={session.pending_human!r}, "
                            f"got APPROVE for {approve!r}"
                        ),
                        "pending_human": session.pending_human,
                    },
                )
            result = await run_confirm(session=session, action=approve)  # type: ignore[arg-type]
        else:
            result = await run_phase_a(
                message=body.message,
                user_jwt=session.user_jwt,
                workbook_id=session.workbook_id,
                provider=provider,
                model=model,
                temperature=temperature,
                llm=None,  # rules/template path; avoid burning LLM quota
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        structured = classify_llm_error(exc, provider=provider, model=model)
        if structured:
            session.stream_events = [
                _sse("error", structured.to_dict()),
                _sse("done", {"verdict": "error", "session_id": session.session_id}),
            ]
            store.update(session)
            raise HTTPException(status_code=429, detail=structured.to_dict()) from exc
        session.stream_events = [
            _sse("error", {"code": "agent_error", "message": str(exc)}),
            _sse("done", {"verdict": "error", "session_id": session.session_id}),
        ]
        store.update(session)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _apply_result_to_session(session, body.message, result)

    return ChatResponse(
        session_id=session.session_id,
        intent=result.get("intent"),
        verdict=result.get("eval_verdict"),
        response_text=result.get("response_text"),
        metrics=result.get("metrics"),
        card=result.get("card"),
        provider=provider,
        model=model,
        temperature=temperature,
        error=result.get("error"),
    )


@router.get("/{session_id}/stream")
async def stream_chat(session_id: str) -> EventSourceResponse:
    store = get_session_store()
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    events = list(session.stream_events or [])
    if not events and session.last_card:
        events = [
            _sse("card", session.last_card),
            _sse("done", {"verdict": (session.last_card or {}).get("verdict"), "session_id": session_id}),
        ]
    if not events:
        events = [
            _sse("error", {"code": "no_events", "message": "No chat turn to stream yet. POST /v1/chat first."}),
            _sse("done", {"session_id": session_id}),
        ]

    async def gen() -> AsyncIterator[dict[str, str]]:
        for ev in events:
            yield ev
            await asyncio.sleep(0)  # flush between events

    return EventSourceResponse(gen())
