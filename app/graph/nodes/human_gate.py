"""Phase C: human confirm before promote/activate (stub)."""

from __future__ import annotations

from typing import Any

from app.graph.state import AgentState


async def human_gate(state: AgentState) -> dict[str, Any]:
    raise NotImplementedError("Phase C human_gate not implemented yet")
