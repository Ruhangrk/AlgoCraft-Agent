"""Phase C lifecycle: confirm → promote / activate (shared by API + chat)."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage

from app.config import get_settings
from app.graph.nodes.activate import activate
from app.graph.nodes.human_gate import human_gate
from app.graph.nodes.promote import promote
from app.graph.nodes.respond import respond
from app.graph.thinking import thought
from app.store.sessions import Session
from app.tools.algocraft_client import AlgocraftClient

Action = Literal["promote", "activate"]


def _apply_patch(state: dict[str, Any], patch: dict[str, Any]) -> None:
    """Merge node patch; concatenate thinking lists (no LangGraph reducer here)."""
    extra = list(patch.get("thinking") or [])
    state.update({k: v for k, v in patch.items() if k != "thinking"})
    if extra:
        state["thinking"] = list(state.get("thinking") or []) + extra


async def run_confirm(
    *,
    session: Session,
    action: Action,
    client: AlgocraftClient | None = None,
) -> dict[str, Any]:
    """
    Run human_gate → promote|activate → respond without the full Phase A/B graph.
    Caller updates the session from the returned state.
    """
    name = session.pending_strategy_name
    if not name and session.last_card:
        name = session.last_card.get("strategy_name") or (
            (session.last_card.get("chosen") or {}).get("name")
        )
    if not name:
        return {
            "error": "no pending strategy name on session (compile first)",
            "eval_verdict": "error",
            "pending_human": session.pending_human,
            "response_text": "Nothing to confirm — compile a strategy first.",
            "card": {"verdict": "error", "pending_human": session.pending_human},
            "thinking": thought(
                "lifecycle",
                "Confirm aborted: no pending strategy name on session.",
                phase="decide",
            )["thinking"],
        }

    settings = get_settings()
    owns = client is None
    if client is None:
        client = AlgocraftClient(base_url=settings.algocraft_api_url, jwt=session.user_jwt)

    state: dict[str, Any] = {
        "messages": [HumanMessage(content=f"APPROVE_{action.upper()}")],
        "session_id": session.session_id,
        "user_jwt": session.user_jwt,
        "workbook_id": session.workbook_id,
        "intent": "codegen_strategy",
        "chosen": {"name": name, "kind": "strategy"},
        "pending_human": session.pending_human,
        "cpp_results": {},
        "metrics": dict(session.last_metrics or {}),
        "thinking": thought(
            "lifecycle",
            f"Phase C confirm started: action={action}, strategy={name}, "
            f"session pending_human={session.pending_human}.",
            phase="start",
            data={"action": action, "name": name},
        )["thinking"],
    }
    config = {"configurable": {"algocraft": client, "confirm_action": action, "llm": None}}

    try:
        gate = await human_gate(state, config)  # type: ignore[arg-type]
        _apply_patch(state, gate)
        if state.get("error"):
            text = state["error"]
            return {
                **state,
                "response_text": text,
                "card": {
                    "intent": "codegen_strategy",
                    "verdict": "error",
                    "pending_human": session.pending_human,
                    "strategy_name": name,
                    "feedback": text,
                },
                "messages": [AIMessage(content=text)],
            }

        if action == "promote":
            mid = await promote(state, config)  # type: ignore[arg-type]
        else:
            mid = await activate(state, config)  # type: ignore[arg-type]
        _apply_patch(state, mid)

        out = await respond(state, config)  # type: ignore[arg-type]
        _apply_patch(state, out)
        return state
    finally:
        if owns:
            await client.aclose()
