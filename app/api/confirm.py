"""Human confirm routes (Phase C)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.graph.lifecycle import run_confirm
from app.store.sessions import Session, get_session_store

router = APIRouter(prefix="/v1/sessions", tags=["confirm"])


class ConfirmRequest(BaseModel):
    action: Literal["promote", "activate"]


class ConfirmResponse(BaseModel):
    session_id: str
    action: Literal["promote", "activate"]
    verdict: str | None = None
    pending_human: str
    response_text: str | None = None
    metrics: dict[str, Any] | None = None
    card: dict[str, Any] | None = None
    thinking: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


def _apply_confirm_to_session(session: Session, message: str, result: dict[str, Any]) -> None:
    session.messages.append({"role": "user", "content": message})
    text = result.get("response_text") or ""
    if text:
        session.messages.append({"role": "assistant", "content": text})
    session.last_metrics = result.get("metrics")
    session.last_card = result.get("card")
    session.last_thinking = list(result.get("thinking") or [])
    if result.get("pending_human") is not None:
        session.pending_human = str(result["pending_human"])
    if session.pending_human == "none":
        session.pending_strategy_name = None
    elif result.get("chosen", {}).get("name"):
        session.pending_strategy_name = str(result["chosen"]["name"])
    get_session_store().update(session)


@router.post("/{session_id}/confirm", response_model=ConfirmResponse)
async def post_confirm(session_id: str, body: ConfirmRequest) -> ConfirmResponse:
    store = get_session_store()
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    if session.pending_human != body.action:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "wrong_gate",
                "message": (
                    f"session pending_human={session.pending_human!r}, "
                    f"got action={body.action!r}"
                ),
                "pending_human": session.pending_human,
            },
        )

    result = await run_confirm(session=session, action=body.action)
    label = f"APPROVE_{body.action.upper()}"
    _apply_confirm_to_session(session, label, result)

    if result.get("error") and result.get("eval_verdict") == "error":
        # Gate/API mismatch already 409; promote/activate C++ failures → 502
        if "promote failed" in str(result["error"]) or "activate failed" in str(result["error"]):
            raise HTTPException(
                status_code=502,
                detail={"code": "cpp_error", "message": result["error"], "body": result.get("cpp_results")},
            )

    return ConfirmResponse(
        session_id=session.session_id,
        action=body.action,
        verdict=result.get("eval_verdict"),
        pending_human=session.pending_human,
        response_text=result.get("response_text"),
        metrics=result.get("metrics"),
        card=result.get("card"),
        thinking=list(result.get("thinking") or []),
        error=result.get("error"),
    )
