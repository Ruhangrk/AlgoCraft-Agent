"""Per-node thinking crumbs for UI (SSE event: thinking)."""

from __future__ import annotations

from typing import Any


def thought(
    agent: str,
    text: str,
    *,
    phase: str = "decide",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Return a state patch that appends one thinking entry.
    AgentState.thinking uses operator.add, so return a one-element list.
    """
    entry: dict[str, Any] = {
        "agent": agent,
        "phase": phase,
        "thought": text,
    }
    if data is not None:
        entry["data"] = data
    return {"thinking": [entry]}


def thoughts(*entries: dict[str, Any]) -> dict[str, Any]:
    """Merge several thought() patches into one state update."""
    merged: list[dict[str, Any]] = []
    for e in entries:
        merged.extend(e.get("thinking") or [])
    return {"thinking": merged}
