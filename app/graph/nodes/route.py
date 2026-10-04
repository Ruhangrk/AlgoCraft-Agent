"""Routing agent — rules + optional LLM when ambiguous."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.graph.nodes._common import get_llm, last_user_text
from app.graph.nodes.entities import (
    extract_strategy_likes,
    extract_tickers,
    looks_like_backtest,
    looks_like_discuss,
    resolve_strategy_mention,
)
from app.graph.state import AgentState
from app.graph.thinking import thought

_GREET_RE = re.compile(
    r"^\s*(hi|hello|hey|yo|sup|thanks|thank you|ok|okay|gm|good morning|good evening)"
    r"[\s!?.]*$",
    re.I,
)
_CANCEL_RE = re.compile(r"\b(cancel|never ?mind|stop create|abort)\b", re.I)
_CREATE_RE = re.compile(
    r"\b(create|generate|write|codegen|build|make)\b.*\bstrateg|"
    r"\bnew\s+strateg|codegen|write a strateg|generate a strateg",
    re.I,
)
_ROUTE_RE = re.compile(
    r"\b(hist\s*run|hist\s*route|routing\s*algo|run\s+(?:the\s+)?router|"
    r"use\s+\w*_?router)\b",
    re.I,
)
_VALID = frozenset({"chat", "discuss", "backtest", "route", "create", "clarify"})

_ROUTE_LLM_SYS = """You route AlgoCraft trading-agent messages.
Return ONLY JSON: {"intent":"chat|discuss|backtest|route|create|clarify","reason":"..."}.
Rules:
- backtest: user wants to run/simulate an existing strategy (tolerate typos like backest).
- route: hist run / router replay.
- create: write/generate a NEW strategy.
- discuss: explain/compare/talk about a strategy (no execute).
- chat: greeting/thanks.
- clarify: truly unclear.
Never invent intents outside the list."""


def _rules_route(text: str, draft: dict[str, Any]) -> tuple[str, str]:
    lower = text.lower().strip()
    if draft.get("active") and draft.get("status") == "interviewing":
        if _CANCEL_RE.search(text):
            return "chat", "User cancelled create interview → chat"
        return "create", "Open create interview — continue gathering requirements"
    if _GREET_RE.match(text) or lower in {"hi", "hello", "hey"}:
        return "chat", "Greeting → chat"
    if _CREATE_RE.search(text):
        return "create", "Explicit create/generate strategy"
    if looks_like_backtest(text):
        return "backtest", "Backtest cue (incl. typos / with-strategy pattern)"
    if _ROUTE_RE.search(text) or (
        "router" in lower and any(w in lower for w in ("run", "hist", "start", "use"))
    ):
        return "route", "Hist/router run"
    if looks_like_discuss(text):
        return "discuss", "Discuss/explain/list about strategies"
    # Named strategy alone → discuss (chatbot-like)
    if extract_strategy_likes(text) and not looks_like_backtest(text):
        return "discuss", "Named strategy token without execute verb → discuss"
    return "clarify", "Ambiguous — will ask LLM if available, else clarify"


async def _llm_route(llm: Any, text: str) -> tuple[str, str] | None:
    try:
        resp = await llm.ainvoke(
            [
                SystemMessage(content=_ROUTE_LLM_SYS),
                HumanMessage(content=text),
            ]
        )
        raw = str(getattr(resp, "content", resp)).strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if fence:
            raw = fence.group(1).strip()
        data = json.loads(raw)
        intent = str(data.get("intent") or "").strip().lower()
        reason = str(data.get("reason") or "llm route")
        if intent in _VALID:
            return intent, f"LLM route: {reason}"
    except Exception:  # noqa: BLE001
        return None
    return None


async def route_intent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    text = last_user_text(state)
    draft = dict(state.get("create_draft") or {})
    tickers = extract_tickers(text)
    strategy_likes = extract_strategy_likes(text)
    topic = resolve_strategy_mention(text, topic=strategy_likes[0] if strategy_likes else None)
    settings = get_settings()
    llm = get_llm(config)

    intent, reason = _rules_route(text, draft)

    if intent == "clarify" and llm is not None:
        llm_hit = await _llm_route(llm, text)
        if llm_hit:
            intent, reason = llm_hit

    if intent == "create" and not (draft.get("active") and draft.get("status") == "interviewing"):
        draft = {
            "active": True,
            "status": "interviewing",
            "ticker": draft.get("ticker") or (tickers[0] if tickers else None),
            "idea": draft.get("idea"),
            "name": draft.get("name"),
        }
    if intent == "chat" and draft.get("status") == "cancelled":
        draft = {"active": False, "status": "cancelled"}
    if intent == "chat" and _CANCEL_RE.search(text):
        draft = {"active": False, "status": "cancelled"}

    out: dict[str, Any] = {
        "intent": intent,  # type: ignore[dict-item]
        "create_draft": draft,
        "tickers": tickers,
        "topic_strategy": topic or (strategy_likes[0] if strategy_likes else None),
        **thought(
            "route",
            f"Routing decision: intent={intent}. {reason}. "
            f"tickers={tickers or []} strategies_mentioned={strategy_likes or []} "
            f"topic={topic}.",
            phase="decide",
            data={
                "intent": intent,
                "tickers": tickers,
                "strategies_mentioned": strategy_likes,
                "topic_strategy": topic,
                "create_active": bool(draft.get("active")),
            },
        ),
    }
    if "max_iterations" not in state:
        out["max_iterations"] = settings.agent_max_iterations
    if "iteration" not in state:
        out["iteration"] = 0
    return out
