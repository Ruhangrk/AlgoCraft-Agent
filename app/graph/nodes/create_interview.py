"""Create-strategy interview — gather ticker (+ idea) before codegen."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.nodes._common import last_user_text
from app.graph.nodes.entities import extract_tickers
from app.graph.nodes.design_code import snake_to_pascal
from app.graph.state import AgentState
from app.graph.thinking import thought
from app.tools.algocraft_client import AlgocraftClient

_NAME_HINT = re.compile(
    r"(?:named|called|name\s*[:=])\s*[`'\"]?([a-z][a-z0-9_]{0,63})[`'\"]?",
    re.I,
)


def _guess_strategy_name(text: str, ticker: str | None) -> str | None:
    m = _NAME_HINT.search(text)
    if m:
        try:
            return AlgocraftClient.validate_strategy_name(m.group(1).lower())
        except ValueError:
            pass
    if ticker:
        base = f"agent_{ticker.lower()}_custom"
        try:
            return AlgocraftClient.validate_strategy_name(base[:64])
        except ValueError:
            return "agent_custom_strategy"
    return None


def _extract_idea(text: str, tickers: list[str]) -> str | None:
    """Strip routing boilerplate; keep a short strategy idea if present."""
    cleaned = text.strip()
    for t in tickers:
        cleaned = re.sub(rf"\b{re.escape(t)}\b", " ", cleaned)
    cleaned = re.sub(
        r"\b(create|generate|write|codegen|build|make|a|new|strategy|please|"
        r"for|on|with|named|called)\b",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")
    if len(cleaned) < 8:
        return None
    return cleaned[:400]


async def create_interview(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    _ = config
    text = last_user_text(state)
    draft = dict(state.get("create_draft") or {})
    if not draft.get("active"):
        draft = {"active": True, "status": "interviewing"}

    tickers = list(state.get("tickers") or []) or extract_tickers(text)
    if tickers and not draft.get("ticker"):
        draft["ticker"] = tickers[0]

    idea = _extract_idea(text, tickers)
    if idea and (not draft.get("idea") or len(idea) > len(str(draft.get("idea") or ""))):
        draft["idea"] = idea
    # If user only sent a ticker while interviewing, keep prior idea
    if tickers and not idea and draft.get("idea"):
        pass

    name = _guess_strategy_name(text, draft.get("ticker"))
    if name:
        draft["name"] = name

    missing: list[str] = []
    if not draft.get("ticker"):
        missing.append("ticker")
    if not draft.get("idea"):
        missing.append("idea")
    draft["missing"] = missing
    draft["active"] = True

    if missing:
        draft["status"] = "interviewing"
        ask_parts = []
        if "ticker" in missing:
            ask_parts.append("**ticker** (e.g. `RELIANCE`, `INFY`, `TCS`)")
        if "idea" in missing:
            ask_parts.append(
                "**strategy idea** in one sentence (entry/exit rules — e.g. "
                "'buy 1 share after 3 red bars, exit next green')"
            )
        prompt = (
            "I can create a new AlgoCraft strategy, but I need a bit more first.\n\n"
            "Please provide:\n- " + "\n- ".join(ask_parts) + "\n\n"
            "Example: `Create a strategy on RELIANCE that buys after 2 consecutive "
            "down bars and exits on the next up bar.`\n\n"
            "Say `cancel` anytime to abort."
        )
        if draft.get("ticker") or draft.get("idea"):
            prompt = (
                "Got it so far: "
                f"ticker=`{draft.get('ticker') or '—'}` · "
                f"idea=`{draft.get('idea') or '—'}`. "
                "Still missing: " + ", ".join(missing) + ".\n\n" + prompt
            )
        return {
            "create_draft": draft,
            "create_ready": False,
            "interview_prompt": prompt,
            "eval_verdict": "need_human",
            "pending_human": "none",
            "feedback": f"create interview waiting on: {', '.join(missing)}",
            **thought(
                "create_interview",
                f"Interview incomplete. missing={missing}. "
                f"draft_ticker={draft.get('ticker')!r} draft_idea={draft.get('idea')!r}.",
                phase="decide",
                data={"missing": missing, "draft": {k: draft.get(k) for k in ("ticker", "idea", "name")}},
            ),
        }

    # Ready to codegen
    draft["status"] = "ready"
    strat_name = draft.get("name") or _guess_strategy_name("", draft.get("ticker")) or "agent_custom_strategy"
    draft["name"] = strat_name
    chosen = {
        "name": strat_name,
        "class_name": snake_to_pascal(strat_name),
        "kind": "strategy",
        "ticker": draft["ticker"],
        "idea": draft["idea"],
        "source": "interview",
    }
    return {
        "create_draft": draft,
        "create_ready": True,
        "chosen": chosen,
        "tickers": [draft["ticker"]],
        "interview_prompt": None,
        "feedback": "Requirements complete — proceeding to design_code.",
        **thought(
            "create_interview",
            f"Requirements complete: ticker={draft['ticker']}, name={strat_name}, "
            f"idea={draft['idea']!r}. Next → design_code.",
            phase="decide",
            data=chosen,
        ),
    }
