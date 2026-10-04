"""Discuss path — focus on named strategy when present; optional LLM."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.config import REPO_ROOT
from app.graph.nodes._common import get_client, get_llm, last_user_text
from app.graph.nodes.entities import resolve_strategy_mention
from app.graph.state import AgentState
from app.graph.thinking import thought

_DISCUSS_SYS = """You are AlgoCraft's strategy desk. Explain the named strategy clearly
for a trader: idea, entries/exits, indicators, session/sizing caveats.
Use only the provided doc + catalog facts. End with one suggested next step
(backtest command or a clarifying question). Keep under 220 words."""


def _load_strategy_doc(name: str) -> str | None:
    path = REPO_ROOT / "docs" / "cpp" / "strategies" / f"{name}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _doc_summary(name: str, doc: str) -> str:
    # Prefer the short Idea / Exit sections if present
    lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
    idea = ""
    exit_ = ""
    for i, ln in enumerate(lines):
        if ln.lower().startswith("## idea") and i + 1 < len(lines):
            idea = lines[i + 1]
        if ln.lower().startswith("## exit") and i + 1 < len(lines):
            exit_ = lines[i + 1]
    bits = [f"### `{name}`"]
    if idea:
        bits.append(f"**Idea:** {idea}")
    if exit_:
        bits.append(f"**Exit:** {exit_}")
    if not idea and not exit_:
        bits.append(doc[:900])
    bits.append(
        f"\nNext: `backtest {name} on <TICKER>` "
        "or ask about another strategy / create a new one."
    )
    return "\n\n".join(bits)


async def discuss(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    text = last_user_text(state)
    strategies = list(state.get("strategy_candidates") or [])
    routers = list(state.get("router_candidates") or [])
    llm = get_llm(config)

    if not strategies:
        try:
            client = get_client(config)
            strategies = list(await client.list_strategies())
            routers = list(await client.list_routers())
        except Exception as exc:  # noqa: BLE001
            return {
                "discuss_summary": f"I couldn't load the strategy catalog ({exc}).",
                "eval_verdict": "error",
                **thought("discuss", f"catalog fetch failed: {exc}", phase="result"),
            }

    topic = state.get("topic_strategy")
    matched = resolve_strategy_mention(text, strategies, topic=topic)

    notes = (
        f"strategies({len(strategies)}): {', '.join(strategies[:16])} | "
        f"routers: {', '.join(routers)}"
    )

    if matched:
        doc = _load_strategy_doc(matched)
        doc_text = doc or f"(no local doc for {matched})"
        if llm is not None:
            try:
                resp = await llm.ainvoke(
                    [
                        SystemMessage(content=_DISCUSS_SYS),
                        HumanMessage(
                            content=(
                                f"User: {text}\n\nStrategy: {matched}\n\n"
                                f"Doc:\n{doc_text[:5000]}\n"
                            )
                        ),
                    ]
                )
                summary = str(getattr(resp, "content", resp)).strip()
            except Exception:  # noqa: BLE001
                summary = (
                    f"Let's talk about **`{matched}`**.\n\n"
                    + _doc_summary(matched, doc_text)
                )
        else:
            summary = (
                f"Let's talk about **`{matched}`**.\n\n"
                + _doc_summary(matched, doc_text)
            )
        return {
            "strategy_candidates": strategies,
            "router_candidates": routers,
            "research_notes": notes,
            "topic_strategy": matched,
            "discuss_summary": summary,
            "eval_verdict": "pass",
            **thought(
                "discuss",
                f"Focused discuss on `{matched}` (local_doc={bool(doc)}, llm={llm is not None}).",
                phase="decide",
                data={"topic_strategy": matched, "used_llm": llm is not None},
            ),
        }

    summary = (
        "Happy to discuss. The engine currently exposes:\n\n"
        f"- **Strategies** ({len(strategies)}): {', '.join(strategies[:24])}"
        f"{'…' if len(strategies) > 24 else ''}\n"
        f"- **Routers**: {', '.join(routers) or 'none'}\n\n"
        f"You asked: {text!r}\n\n"
        "Name a strategy (e.g. `two_consecutive_bars`) and I’ll dig in, "
        "or say `backtest <strategy> on <TICKER>`."
    )
    return {
        "strategy_candidates": strategies,
        "router_candidates": routers,
        "research_notes": notes,
        "discuss_summary": summary,
        "eval_verdict": "pass",
        **thought(
            "discuss",
            "General discuss (no specific strategy matched).",
            phase="decide",
            data={"strategy_count": len(strategies)},
        ),
    }
