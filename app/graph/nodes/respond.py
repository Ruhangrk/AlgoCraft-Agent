"""Respond node — user-facing summary + card JSON."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState


async def respond(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    _ = config
    verdict = state.get("eval_verdict") or "error"
    metrics = state.get("metrics") or {}
    chosen = state.get("chosen") or {}
    feedback = state.get("feedback") or ""
    intent = state.get("intent") or "unknown"

    card = {
        "intent": intent,
        "verdict": verdict,
        "metrics": metrics,
        "chosen": chosen,
        "feedback": feedback,
        "workbook_id": state.get("workbook_id"),
    }

    if intent == "route":
        summary = (
            f"Hist/route run via `{chosen.get('router')}` on {chosen.get('anchor_date')}: "
            f"verdict={verdict}, fills={metrics.get('fills')}, pnl_paise={metrics.get('pnl_paise')}."
        )
    else:
        summary = (
            f"Backtest `{chosen.get('strategy')}` on {chosen.get('ticker')} "
            f"({chosen.get('session_from')}→{chosen.get('session_to')}): "
            f"verdict={verdict}, fills={metrics.get('fills')}, pnl_paise={metrics.get('pnl_paise')}."
        )
    if feedback:
        summary += f" Note: {feedback}"

    return {
        "card": card,
        "response_text": summary,
        "messages": [AIMessage(content=summary)],
        "_retry": False,
    }
