"""Phase B: emit Strategy sources (name, class_name, hpp, cpp)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.graph.nodes._common import get_llm, last_user_text, llm_ainvoke, llm_content_text
from app.graph.state import AgentState
from app.llm.prompts import CODEGEN_COMPACT_RULES, DESIGN_CODE_SYSTEM
from app.graph.nodes.strategy_sources import (
    ensure_required_includes,
    patch_common_llm_cpp_mistakes,
    validate_strategy_sources,
)
from app.tools.algocraft_client import AlgocraftClient
from app.graph.thinking import thought

_NAME_HINT = re.compile(
    r"(?:named|called|name\s*[:=])\s*[`'\"]?([a-z][a-z0-9_]{0,63})[`'\"]?",
    re.I,
)
_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


def snake_to_pascal(name: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in name.split("_") if p)


_SKIP_TOKENS = frozenset(
    {
        "codegen",
        "generate",
        "strategy",
        "strategies",
        "write",
        "create",
        "please",
        "with",
        "that",
        "this",
        "from",
        "named",
        "called",
        "name",
        "make",
        "build",
        "simple",
        "smoke",
        "test",
    }
)


def _guess_name(text: str) -> str:
    m = _NAME_HINT.search(text)
    if m:
        return m.group(1).lower()
    for tok in re.findall(r"\b[a-z][a-z0-9_]{2,63}\b", text.lower()):
        if tok in _SKIP_TOKENS:
            continue
        try:
            AlgocraftClient.validate_strategy_name(tok)
            return tok
        except ValueError:
            continue
    return "agent_smoke_churn"


def _detect_pattern(idea: str) -> str:
    """Map a short idea to a known simple template (else churn)."""
    t = idea.lower()
    if any(k in t for k in ("09:20", "9:20", "after open", "open clip", "single clip")):
        return "open_clip"
    if ("two green" in t or "2 green" in t or "consecutive green" in t) and "red" in t:
        return "two_green"
    if ("two red" in t or "2 red" in t or "consecutive red" in t) and "green" in t:
        return "two_red"
    if "consecutive green" in t or "2 consecutive green" in t:
        return "two_green"
    if "consecutive red" in t or "2 consecutive red" in t:
        return "two_red"
    return "churn"


def _base_hpp(class_name: str, extra_fields: str) -> str:
    return f"""#pragma once

#include "algocraft/strategies/strategy.hpp"

namespace algocraft {{

class {class_name} final : public Strategy {{
public:
  void configure(const StrategyConfig&, IndicatorLibrary&) override;
  void on_bar(const BarEvent&, const PortfolioView&, std::vector<OrderIntent>&) override;
  void on_fill(const FillEvent&) override {{}}
  void on_order_update(const OrderUpdate&) override {{}}
  bool should_exit() const override {{ return false; }}
  StrategyMetadata metadata() const override;

private:
  StrategyConfig config_{{}};
{extra_fields}}};

}}  // namespace algocraft
"""


def _template_sources(name: str, class_name: str, idea: str) -> tuple[dict[str, str], str]:
    """
    Deterministic simple strategies that always compile against real AlgoCraft headers.
    Returns (sources, pattern).
    """
    pattern = _detect_pattern(idea)
    if pattern == "two_red":
        hpp = _base_hpp(class_name, "  int red_streak_{0};\n")
        on_bar = f"""
void {class_name}::on_bar(const BarEvent& bar, const PortfolioView& pf,
                          std::vector<OrderIntent>& out) {{
  if (bar.symbol_id != config_.symbol_id || bar.resolution != BarResolution::OneMin) return;
  const int minute = ist_minute_of_day(bar.timestamp);
  if (minute >= kFlattenMin) {{
    if (pf.position.shares() > 0)
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    red_streak_ = 0;
    return;
  }}
  const bool red = bar.close.paise() < bar.open.paise();
  const bool green = bar.close.paise() > bar.open.paise();
  if (pf.position.shares() == 0) {{
    red_streak_ = red ? red_streak_ + 1 : 0;
    if (red_streak_ >= 2) {{
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Buy, Quantity::from_shares(1)));
      red_streak_ = 0;
    }}
  }} else if (green) {{
    out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    red_streak_ = 0;
  }}
}}
"""
    elif pattern == "two_green":
        hpp = _base_hpp(class_name, "  int green_streak_{0};\n")
        on_bar = f"""
void {class_name}::on_bar(const BarEvent& bar, const PortfolioView& pf,
                          std::vector<OrderIntent>& out) {{
  if (bar.symbol_id != config_.symbol_id || bar.resolution != BarResolution::OneMin) return;
  const int minute = ist_minute_of_day(bar.timestamp);
  if (minute >= kFlattenMin) {{
    if (pf.position.shares() > 0)
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    green_streak_ = 0;
    return;
  }}
  const bool green = bar.close.paise() > bar.open.paise();
  const bool red = bar.close.paise() < bar.open.paise();
  if (pf.position.shares() == 0) {{
    green_streak_ = green ? green_streak_ + 1 : 0;
    if (green_streak_ >= 2) {{
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Buy, Quantity::from_shares(1)));
      green_streak_ = 0;
    }}
  }} else if (red) {{
    out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    green_streak_ = 0;
  }}
}}
"""
    elif pattern == "open_clip":
        hpp = _base_hpp(class_name, "  bool entered_{false};\n")
        on_bar = f"""
void {class_name}::on_bar(const BarEvent& bar, const PortfolioView& pf,
                          std::vector<OrderIntent>& out) {{
  if (bar.symbol_id != config_.symbol_id || bar.resolution != BarResolution::OneMin) return;
  const int minute = ist_minute_of_day(bar.timestamp);
  if (minute >= kFlattenMin) {{
    if (pf.position.shares() > 0)
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    return;
  }}
  if (!entered_ && minute >= kEntryMin && pf.position.shares() == 0) {{
    out.push_back(make_intent(kSid, config_.symbol_id, Side::Buy, Quantity::from_shares(1)));
    entered_ = true;
  }}
}}
"""
    else:
        pattern = "churn"
        hpp = _base_hpp(class_name, "")
        on_bar = f"""
void {class_name}::on_bar(const BarEvent& bar, const PortfolioView& pf,
                          std::vector<OrderIntent>& out) {{
  if (bar.symbol_id != config_.symbol_id || bar.resolution != BarResolution::OneMin) return;
  const int minute = ist_minute_of_day(bar.timestamp);
  if (minute >= kFlattenMin) {{
    if (pf.position.shares() > 0)
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    return;
  }}
  if (pf.position.shares() > 0)
    out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
  out.push_back(make_intent(kSid, config_.symbol_id, Side::Buy, Quantity::from_shares(1)));
}}
"""

    extras = ""
    if pattern == "open_clip":
        extras = "constexpr int kEntryMin = 9 * 60 + 20;  // 09:20 IST\n"

    cpp = f"""#include "algocraft/strategies/{name}.hpp"

#include "algocraft/domain/bar_resolution.hpp"
#include "algocraft/domain/session_clock.hpp"
#include "algocraft/strategies/make_intent.hpp"

namespace algocraft {{
namespace {{
constexpr StrategyId kSid = StrategyId::from(9001);
constexpr int kFlattenMin = 15 * 60 + 15;  // 15:15 IST
{extras}}}

void {class_name}::configure(const StrategyConfig& config, IndicatorLibrary&) {{
  config_ = config;
}}
{on_bar}
StrategyMetadata {class_name}::metadata() const {{
  return {{"{name}", "1.0.0", TradingMode::Mis, BarResolution::OneMin, {{}}}};
}}

}}  // namespace algocraft
"""
    return {"hpp": hpp, "cpp": cpp}, pattern


def _parse_codegen_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = _JSON_FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("codegen JSON must be an object")
    return data


async def design_code(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    text = last_user_text(state)
    settings = get_settings()
    llm = get_llm(config)
    draft = dict(state.get("create_draft") or {})
    prior = dict(state.get("chosen") or {})

    # Prefer interview fields
    if prior.get("name"):
        preferred_name = str(prior["name"])
    elif draft.get("name"):
        preferred_name = str(draft["name"])
    else:
        preferred_name = _guess_name(text)

    idea = str(prior.get("idea") or draft.get("idea") or text)
    pattern = _detect_pattern(idea)

    def _from_template(name: str, class_name: str, *, source: str) -> dict[str, Any]:
        src, used_pattern = _template_sources(name, class_name, idea)
        return {
            "name": name,
            "class_name": class_name,
            "kind": "strategy",
            "hpp": src["hpp"],
            "cpp": src["cpp"],
            "source": source,
            "pattern": used_pattern,
            "ticker": prior.get("ticker") or draft.get("ticker"),
            "idea": idea,
        }

    chosen: dict[str, Any]
    # LLM-first when available. Pattern/churn templates are fallback only.
    if llm is None:
        name = preferred_name
        try:
            AlgocraftClient.validate_strategy_name(name)
        except ValueError:
            name = _guess_name(text)
        class_name = str(prior.get("class_name") or snake_to_pascal(name))
        src_label = "template_pattern" if pattern != "churn" else "template"
        chosen = _from_template(name, class_name, source=src_label)
    else:
        # Compact rules only — full docs/cpp dumps exhaust Groq TPM / max_tokens.
        prompt = (
            f"## Rules\n{CODEGEN_COMPACT_RULES.strip()}\n\n"
            f"## Requirements\n"
            f"preferred_name={preferred_name}\n"
            f"ticker={prior.get('ticker') or draft.get('ticker')}\n"
            f"idea={idea}\n"
            f"user_message={text}\n\n"
            "Implement the idea above (not a generic churn smoke test).\n"
            "Return ONLY JSON with keys: name, class_name, kind, hpp, cpp."
        )
        bound = llm.bind(max_tokens=5500) if hasattr(llm, "bind") else llm
        chosen = {}
        last_err = "design failed"
        for attempt in (1, 2, 3):
            human = prompt
            if attempt == 2 and "empty" in last_err.lower():
                human += (
                    "\n\nRETRY: previous reply was empty/truncated. "
                    "Emit complete JSON now with short C++. No preamble."
                )
            elif attempt >= 2:
                human += (
                    f"\n\nRETRY ({attempt}): previous sources rejected: {last_err}\n"
                    "Fix by including real strategy.hpp and AlgoCraft types only."
                )
            try:
                resp = await llm_ainvoke(
                    bound,
                    [
                        SystemMessage(content=DESIGN_CODE_SYSTEM),
                        HumanMessage(content=human),
                    ],
                    label=f"design_code.attempt{attempt}",
                )
                content = llm_content_text(getattr(resp, "content", resp))
                meta = dict(getattr(resp, "response_metadata", None) or {})
                if not content:
                    raise ValueError(
                        "LLM returned empty content "
                        f"(finish_reason={meta.get('finish_reason')!r})"
                    )
                data = _parse_codegen_json(content)
                name = str(data.get("name") or preferred_name).lower()
                AlgocraftClient.validate_strategy_name(name)
                class_name = str(data.get("class_name") or snake_to_pascal(name))
                hpp = str(data.get("hpp") or "")
                cpp = str(data.get("cpp") or "")
                if not hpp.strip() or not cpp.strip():
                    raise ValueError("LLM omitted hpp/cpp")
                cpp = patch_common_llm_cpp_mistakes(ensure_required_includes(name, cpp))
                verr = validate_strategy_sources(name, hpp, cpp)
                if verr:
                    raise ValueError(verr)
                chosen = {
                    "name": name,
                    "class_name": class_name,
                    "kind": "strategy",
                    "hpp": hpp,
                    "cpp": cpp,
                    "source": "llm",
                    "ticker": prior.get("ticker") or draft.get("ticker"),
                    "idea": idea,
                }
                break
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                chosen = {}
        if not chosen:
            name = preferred_name
            class_name = snake_to_pascal(name)
            chosen = _from_template(name, class_name, source="template_fallback")
            chosen["design_error"] = last_err

    draft = {
        **draft,
        "active": True,
        "status": "designing",
        "name": chosen["name"],
        "ticker": chosen.get("ticker") or draft.get("ticker"),
        "idea": idea,
    }

    note = (
        f"Emitted strategy name={chosen['name']} class={chosen['class_name']} "
        f"source={chosen.get('source')} ticker={chosen.get('ticker')} "
        f"(hpp/cpp ready for compile)."
    )
    if chosen.get("design_error"):
        note += f" design_error={chosen['design_error'][:300]}"

    return {
        "chosen": chosen,
        "create_draft": draft,
        "compile_attempts": 0,
        "max_iterations": state.get("max_iterations") or settings.agent_max_iterations,
        "pending_human": "none",
        "error": None,
        "feedback": (
            f"design used template_fallback: {chosen['design_error']}"
            if chosen.get("source") == "template_fallback" and chosen.get("design_error")
            else None
        ),
        **thought(
            "design_code",
            note,
            phase="decide",
            data={
                "name": chosen["name"],
                "class_name": chosen["class_name"],
                "source": chosen.get("source"),
                "ticker": chosen.get("ticker"),
                "design_error": chosen.get("design_error"),
            },
        ),
    }
