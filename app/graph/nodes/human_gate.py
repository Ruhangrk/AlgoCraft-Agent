"""Phase C: validate pending_human before promote/activate."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState
from app.graph.thinking import thought

Action = Literal["promote", "activate"]


def require_pending(state: AgentState, action: Action) -> str | None:
    """Return error string if gate fails, else None."""
    pending = state.get("pending_human") or "none"
    if pending != action:
        return (
            f"human_gate: expected pending_human={action!r}, got {pending!r}. "
            "Compile must succeed first; confirm actions must match the pending gate."
        )
    name = (state.get("chosen") or {}).get("name")
    if not name:
        return "human_gate: missing chosen.name for promote/activate"
    return None


async def human_gate(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """
    Gate node for graph resume paths (APPROVE_*).
    Expects `configurable["confirm_action"]` = promote|activate.
    """
    _ = config
    conf = (config or {}).get("configurable") or {}
    action = conf.get("confirm_action")
    if action not in ("promote", "activate"):
        return {
            "error": "human_gate: configurable['confirm_action'] must be promote|activate",
            "eval_verdict": "error",
            **thought(
                "human_gate",
                "Missing/invalid confirm_action in configurable.",
                phase="decide",
            ),
        }
    err = require_pending(state, action)  # type: ignore[arg-type]
    if err:
        return {
            "error": err,
            "eval_verdict": "error",
            "feedback": err,
            **thought("human_gate", err, phase="decide"),
        }
    return {
        "error": None,
        "feedback": f"Human approved {action}.",
        **thought(
            "human_gate",
            f"Gate open: pending_human matched action={action} for "
            f"`{(state.get('chosen') or {}).get('name')}`.",
            phase="decide",
            data={"action": action, "name": (state.get("chosen") or {}).get("name")},
        ),
    }
