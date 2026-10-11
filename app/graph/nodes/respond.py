"""Respond node — draft user-facing summary + optional LLM polish + card JSON."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.graph.nodes._common import get_llm, last_user_text, llm_content_text
from app.graph.state import AgentState
from app.graph.thinking import thought, thoughts
from app.llm.errors import is_rate_limit_error
from app.llm.prompts import RESPOND_SYSTEM

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


def _format_inr_rupees(rupees: int) -> str:
    """Indian-style thousands grouping: 100000 → 1,00,000."""
    s = str(abs(int(rupees)))
    if len(s) <= 3:
        body = s
    else:
        last3, rest = s[-3:], s[:-3]
        parts: list[str] = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        body = ",".join(reversed(parts)) + "," + last3
    return ("-₹" if rupees < 0 else "₹") + body


def _capital_line(chosen: dict[str, Any]) -> str:
    """Human-readable capital from chosen.capital_paise."""
    raw = chosen.get("capital_paise")
    if raw is None:
        return ""
    try:
        paise = int(raw)
    except (TypeError, ValueError):
        return ""
    if paise % 100 == 0:
        return f"Total capital used: {_format_inr_rupees(paise // 100)}."
    return f"Total capital used: {_format_inr_rupees(paise // 100)}.{paise % 100:02d}."


def _lane_label(
    *,
    intent: str,
    pending: str,
    metrics: dict[str, Any],
    interview_prompt: Any,
) -> str:
    if metrics.get("activated"):
        return "activate (Phase C — catalog enabled)"
    if metrics.get("promoted"):
        return "promote (Phase C — catalog enabled=0)"
    if intent == "create" and interview_prompt:
        return "create interview (gathering ticker/idea)"
    if intent in ("create", "codegen_strategy") and pending == "promote":
        return "create compile (awaiting human promote)"
    if intent in ("create", "codegen_strategy"):
        return "create strategy"
    if intent == "backtest":
        return "backtest existing strategy"
    if intent == "route":
        return "hist / router run"
    if intent == "discuss":
        return "discuss / explain"
    if intent == "chat":
        return "chat / greeting"
    if intent in ("clarify", "unknown"):
        return "clarify (need user to pick a lane)"
    return intent


def _pipeline_hint(state: AgentState, intent: str) -> str:
    agents: list[str] = []
    for crumb in state.get("thinking") or []:
        if isinstance(crumb, dict):
            agent = str(crumb.get("agent") or "").strip()
            if agent and agent not in agents and agent != "respond":
                agents.append(agent)
    if agents:
        return " → ".join(agents) + " → respond"
    # Fallback when thinking is empty (e.g. Phase C lifecycle)
    if intent in ("backtest", "route"):
        return "route → research → propose → execute → evaluate → respond"
    if intent == "discuss":
        return "route → discuss → respond"
    if intent in ("create", "codegen_strategy"):
        return "route → create_interview → (design_code → compile_loop) → respond"
    return "route → respond"


def _build_draft(
    state: AgentState,
) -> tuple[str, str, dict[str, Any]]:
    """Deterministic draft reply + verdict + card (no LLM)."""
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
            summary = "Hi — I’m the AlgoCraft trading agent.\n\n" + _CLARIFY
    elif intent in ("clarify", "unknown"):
        user = last_user_text(state)
        summary = f"I’m not sure what to do with {user!r}.\n\n" + _CLARIFY
    elif intent == "route":
        summary = (
            f"Hist/route via `{chosen.get('router')}` on {chosen.get('anchor_date')}: "
            f"verdict={verdict}, fills={metrics.get('fills')}, "
            f"pnl_paise={metrics.get('pnl_paise')}, events={metrics.get('event_count')}."
        )
        cap = _capital_line(chosen)
        if cap:
            summary += f"\n{cap}"
        card["events_preview"] = (state.get("cpp_results") or {}).get("events", [])[:20]
        if chosen.get("capital_paise") is not None:
            card["capital_paise"] = chosen.get("capital_paise")
        if feedback:
            summary += f"\nNote: {feedback}"
    elif intent == "backtest":
        summary = (
            f"Backtest `{chosen.get('strategy')}` on `{chosen.get('ticker')}` "
            f"({chosen.get('session_from')}→{chosen.get('session_to')}): "
            f"verdict={verdict}, fills={metrics.get('fills')}, "
            f"pnl_paise={metrics.get('pnl_paise')}."
        )
        cap = _capital_line(chosen)
        if cap:
            summary += f"\n{cap}"
        if chosen.get("capital_paise") is not None:
            card["capital_paise"] = chosen.get("capital_paise")
        if feedback:
            summary += f"\nNote: {feedback}"
    else:
        summary = feedback or _CLARIFY

    return summary, verdict, card


def _polish_prompt(
    *,
    user_text: str,
    lane: str,
    pipeline: str,
    draft: str,
    card: dict[str, Any],
    error: str | None,
) -> str:
    # Keep the LLM context tight; card already excludes hpp/cpp.
    facts = {
        "intent": card.get("intent"),
        "verdict": card.get("verdict"),
        "pending_human": card.get("pending_human"),
        "metrics": card.get("metrics"),
        "chosen": card.get("chosen"),
        "feedback": card.get("feedback"),
        "strategy_name": card.get("strategy_name"),
        "create_draft": card.get("create_draft"),
        "workbook_id": card.get("workbook_id"),
        "capital_paise": card.get("capital_paise")
        or (card.get("chosen") or {}).get("capital_paise"),
        "error": error,
    }
    asked = (user_text or "").strip() or "(empty — no user text found in this turn)"
    our_answer = (draft or "").strip() or "(empty draft)"
    return (
        "You are helping as the AlgoCraft assistant.\n"
        "Below are attached: (A) the user's question and (B) our answer/result for "
        "this turn. Write the final reply to the user the way a professional agent would.\n\n"
        "--- A) USER QUESTION ---\n"
        f"{asked}\n\n"
        "--- B) OUR ANSWER / FINAL RESULT (authoritative draft) ---\n"
        f"{our_answer}\n\n"
        "--- CONTEXT (do not invent beyond this) ---\n"
        f"Lane: {lane}\n"
        f"Pipeline: {pipeline}\n"
        f"Facts: {facts}\n\n"
        "Now write the final user-facing message."
    )


async def _polish_with_llm(
    llm: Any,
    *,
    user_text: str,
    lane: str,
    pipeline: str,
    draft: str,
    card: dict[str, Any],
    error: str | None,
) -> str:
    resp = await llm.ainvoke(
        [
            SystemMessage(content=RESPOND_SYSTEM),
            HumanMessage(
                content=_polish_prompt(
                    user_text=user_text,
                    lane=lane,
                    pipeline=pipeline,
                    draft=draft,
                    card=card,
                    error=error,
                )
            ),
        ]
    )
    text = llm_content_text(getattr(resp, "content", resp))
    if not text:
        raise ValueError("LLM respond polish returned empty content")
    return text


async def respond(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    draft_summary, verdict, card = _build_draft(state)
    intent = str(card.get("intent") or state.get("intent") or "clarify")
    pending = str(card.get("pending_human") or state.get("pending_human") or "none")
    metrics = dict(card.get("metrics") or {})
    draft = state.get("create_draft") or {}
    user_text = last_user_text(state)
    lane = _lane_label(
        intent=intent,
        pending=pending,
        metrics=metrics,
        interview_prompt=state.get("interview_prompt"),
    )
    pipeline = _pipeline_hint(state, intent)

    summary = draft_summary
    llm = get_llm(config)
    polish_note = "template only (no llm)"
    if llm is not None:
        try:
            summary = await _polish_with_llm(
                llm,
                user_text=user_text,
                lane=lane,
                pipeline=pipeline,
                draft=draft_summary,
                card=card,
                error=state.get("error"),
            )
            polish_note = "llm polished"
        except Exception as exc:  # noqa: BLE001
            if is_rate_limit_error(exc):
                raise
            summary = draft_summary
            polish_note = f"llm polish failed ({type(exc).__name__}: {exc}); using draft"

    crumbs = thoughts(
        thought(
            "respond",
            f"Drafted reply for lane={lane} ({len(draft_summary)} chars).",
            phase="decide",
            data={"intent": intent, "verdict": verdict, "lane": lane, "pipeline": pipeline},
        ),
        thought(
            "respond",
            f"Final reply ready ({polish_note}, {len(summary)} chars).",
            phase="end",
            data={
                "intent": intent,
                "verdict": verdict,
                "polished": polish_note == "llm polished",
            },
        ),
    )
    return {
        "card": card,
        "response_text": summary,
        "eval_verdict": verdict,
        "create_draft": draft,
        "messages": [AIMessage(content=summary)],
        "_retry": False,
        **crumbs,
    }
