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
    pending = state.get("pending_human") or "none"
    error = state.get("error")

    card = {
        "intent": intent,
        "verdict": verdict,
        "metrics": metrics,
        "chosen": {
            k: v
            for k, v in chosen.items()
            if k not in ("hpp", "cpp")  # keep card small; sources in cpp_results path
        },
        "feedback": feedback,
        "workbook_id": state.get("workbook_id"),
        "pending_human": pending,
    }
    if intent == "codegen_strategy" or metrics.get("promoted") or metrics.get("activated"):
        card["compile_attempts"] = state.get("compile_attempts")
        card["sandbox_dir"] = (state.get("cpp_results") or {}).get("sandbox_dir")
        if chosen.get("name"):
            card["strategy_name"] = chosen["name"]
        for key in ("hpp_path", "cpp_path"):
            if (state.get("cpp_results") or {}).get(key):
                card[key] = (state.get("cpp_results") or {}).get(key)
            elif metrics.get(key):
                card[key] = metrics.get(key)

    if metrics.get("activated"):
        name = metrics.get("name") or chosen.get("name") or "?"
        summary = (
            f"Activated `{name}` in catalog (enabled=1). "
            f"Rebuild + `scripts/serve --restart` required to load into the registry."
        )
        if feedback:
            summary += f" {feedback}"
    elif metrics.get("promoted"):
        name = metrics.get("name") or chosen.get("name") or "?"
        summary = (
            f"Promoted `{name}` into the tree (catalog enabled=0). "
            f"Confirm activate next when ready. "
            f"Paths: hpp={metrics.get('hpp_path')}, cpp={metrics.get('cpp_path')}."
        )
        if feedback:
            summary += f" {feedback}"
    elif intent == "codegen_strategy":
        name = chosen.get("name") or "?"
        if verdict == "need_human" and pending == "promote":
            summary = (
                f"Compiled strategy `{name}` "
                f"(attempts={state.get('compile_attempts')}). "
                f"Ready for human confirm → promote (catalog enabled=0). "
                f"Activate + rebuild/restart still required later."
            )
        elif verdict == "need_human" and pending == "activate":
            summary = (
                f"Strategy `{name}` awaiting activate confirm. "
                f"Then rebuild + restart serve."
            )
        else:
            summary = (
                f"Codegen `{name}`: verdict={verdict}, "
                f"attempts={state.get('compile_attempts')}."
            )
            if error:
                summary += f" Error: {error}"
        if feedback and verdict == "need_human":
            summary += f" {feedback}"
    elif intent == "route":
        summary = (
            f"Hist/route run via `{chosen.get('router')}` on {chosen.get('anchor_date')}: "
            f"verdict={verdict}, fills={metrics.get('fills')}, pnl_paise={metrics.get('pnl_paise')}, "
            f"events={metrics.get('event_count')}, selected={metrics.get('selected')}."
        )
        card["events_preview"] = (state.get("cpp_results") or {}).get("events", [])[:20]
        if feedback:
            summary += f" Note: {feedback}"
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
