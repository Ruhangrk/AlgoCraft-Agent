"""Phase C: promote compiled sandbox strategy into the C++ tree (enabled=0)."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.nodes._common import get_client
from app.graph.nodes.human_gate import require_pending
from app.graph.state import AgentState


async def promote(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    err = require_pending(state, "promote")
    if err:
        return {
            "error": err,
            "eval_verdict": "error",
            "pending_human": state.get("pending_human") or "none",
            "cpp_results": state.get("cpp_results") or {},
        }

    client = get_client(config)
    name = str((state.get("chosen") or {})["name"])
    try:
        raw = await client.agent_promote(name)
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"promote failed: {exc}",
            "eval_verdict": "error",
            "pending_human": "promote",
            "cpp_results": {"ok": False, "error": str(exc)},
            "feedback": str(exc),
        }

    note = str(
        (raw or {}).get("note")
        or "Promoted with enabled=0. Confirm activate next; then rebuild + restart serve."
    )
    return {
        "cpp_results": raw,
        "eval_verdict": "need_human",
        "pending_human": "activate",
        "error": None,
        "feedback": note,
        "metrics": {
            "promoted": True,
            "name": name,
            "enabled": False,
            "hpp_path": (raw or {}).get("hpp_path"),
            "cpp_path": (raw or {}).get("cpp_path"),
            "id": (raw or {}).get("id"),
        },
    }
