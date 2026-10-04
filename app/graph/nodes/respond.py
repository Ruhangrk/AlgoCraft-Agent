"""Respond node — user-facing summary + card JSON."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.graph.nodes._common import last_user_text
from app.graph.state import AgentState
from app.graph.thinking import thought

_CLARIFY = (
    "I can help with three things:\n"
    "1. **Backtest** an existing strategy — e.g. "
    "`backtest hammer_reversal on RELIANCE`\n"
    "2. **Discuss** strategies/routers — e.g. `explain ema_crossover` or "
    "`list strategies`\n"
    "3. **Create** a new strategy — e.g. "
    "`create a strategy on INFY that buys after 2 red bars`\n\n"
    "Say which you’d like (I won’t run a backtest unless you ask)."
)


async def respond(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    _ = config
    verdict = state.get("eval_verdict")
    metrics = state.get("metrics") or {}
    chosen = state.get("chosen") or {}
    feedback = state.get("feedback") or ""
    intent = state.get("intent") or "clarify"
    pending = state.get("pending_human") or "none"
    error = state.get("error")
    draft = state.get("create_draft") or {}

    if verdict is None:
        verdict = "pass" if intent in ("chat", "discuss", "clarify") else "error"

    card: dict[str, Any] = {
        "intent": intent,
        "verdict": verdict,
        "metrics": metrics,
        "chosen": {k: v for k, v in chosen.items() if k not in ("hpp", "cpp")},
        "feedback": feedback,
        "workbook_id": state.get("workbook_id"),
        "pending_human": pending,
        "create_draft": {
            k: draft.get(k)
            for k in ("active", "status", "ticker", "idea", "name", "missing")
            if draft
        }
        or None,
    }

    if intent == "create" or metrics.get("promoted") or metrics.get("activated") or chosen.get("name"):
        card["compile_attempts"] = state.get("compile_attempts")
        card["sandbox_dir"] = (state.get("cpp_results") or {}).get("sandbox_dir")
        if chosen.get("name"):
            card["strategy_name"] = chosen["name"]
        for key in ("hpp_path", "cpp_path"):
            val = (state.get("cpp_results") or {}).get(key) or metrics.get(key)
            if val:
                card[key] = val

    if metrics.get("activated"):
        name = metrics.get("name") or chosen.get("name") or "?"
        summary = (
            f"Activated `{name}` in catalog (enabled=1). "
            "Rebuild + `scripts/serve --restart` so the registry loads it."
        )
        if feedback:
            summary += f"\n{feedback}"
    elif metrics.get("promoted"):
        name = metrics.get("name") or chosen.get("name") or "?"
        summary = (
            f"Promoted `{name}` (catalog enabled=0).\n"
            f"Paths: `{metrics.get('hpp_path')}`, `{metrics.get('cpp_path')}`.\n"
            "Confirm **activate** when ready, then rebuild + restart serve."
        )
    elif intent == "create" and state.get("interview_prompt"):
        summary = str(state["interview_prompt"])
        verdict = "need_human"
        card["verdict"] = verdict
    elif intent in ("create", "codegen_strategy") and chosen.get("name"):
        name = chosen.get("name") or "?"
        if verdict == "need_human" and pending == "promote":
            summary = (
                f"Compiled strategy `{name}` "
                f"(attempts={state.get('compile_attempts')}).\n"
                f"Ticker context: `{draft.get('ticker') or chosen.get('ticker') or '—'}`.\n"
                "Next: confirm **promote** (enabled=0). Activate + rebuild/restart come after."
            )
        else:
            summary = f"Create `{name}`: verdict={verdict}."
            if error:
                summary += f"\nError: {error}"
            if feedback:
                summary += f"\n{feedback}"
    elif intent == "discuss" or state.get("discuss_summary"):
        summary = str(state.get("discuss_summary") or "Happy to discuss strategies.")
    elif intent == "chat":
        if draft.get("status") == "cancelled":
            summary = "Create interview cancelled. " + _CLARIFY
        else:
            summary = (
                "Hi — I’m the AlgoCraft trading agent.\n\n" + _CLARIFY
            )
    elif intent in ("clarify", "unknown"):
        user = last_user_text(state)
        summary = f"I’m not sure what to do with {user!r}.\n\n" + _CLARIFY
    elif intent == "route":
        summary = (
            f"Hist/route via `{chosen.get('router')}` on {chosen.get('anchor_date')}: "
            f"verdict={verdict}, fills={metrics.get('fills')}, "
            f"pnl_paise={metrics.get('pnl_paise')}, events={metrics.get('event_count')}."
        )
        card["events_preview"] = (state.get("cpp_results") or {}).get("events", [])[:20]
        if feedback:
            summary += f"\nNote: {feedback}"
    elif intent == "backtest":
        summary = (
            f"Backtest `{chosen.get('strategy')}` on `{chosen.get('ticker')}` "
            f"({chosen.get('session_from')}→{chosen.get('session_to')}): "
            f"verdict={verdict}, fills={metrics.get('fills')}, "
            f"pnl_paise={metrics.get('pnl_paise')}."
        )
        if feedback:
            summary += f"\nNote: {feedback}"
    else:
        summary = feedback or _CLARIFY

    return {
        "card": card,
        "response_text": summary,
        "eval_verdict": verdict,
        "create_draft": draft,
        "messages": [AIMessage(content=summary)],
        "_retry": False,
        **thought(
            "respond",
            f"Reply for intent={intent}, verdict={verdict}, pending={pending} "
            f"({len(summary)} chars).",
            phase="end",
            data={"intent": intent, "verdict": verdict},
        ),
    }
