"""Phase C: activate promoted strategy in catalog (enabled=1)."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.nodes._common import get_client
from app.graph.nodes.human_gate import require_pending
from app.graph.state import AgentState

_RESTART_NOTE = (
    "Activated in catalog. Rebuild C++ and run `scripts/serve --restart` "
    "so the in-process registry loads the new strategy (no dlopen yet)."
)


async def activate(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    err = require_pending(state, "activate")
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
        raw = await client.agent_activate(name, enabled=True)
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"activate failed: {exc}",
            "eval_verdict": "error",
            "pending_human": "activate",
            "cpp_results": {"ok": False, "error": str(exc)},
            "feedback": str(exc),
        }

    note = str((raw or {}).get("note") or _RESTART_NOTE)
    return {
        "cpp_results": raw,
        "eval_verdict": "pass",
        "pending_human": "none",
        "error": None,
        "feedback": note,
        "metrics": {
            "activated": True,
            "name": name,
            "enabled": True,
            "id": (raw or {}).get("id"),
        },
    }
