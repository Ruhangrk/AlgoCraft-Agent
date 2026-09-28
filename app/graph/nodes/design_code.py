"""Phase B: emit Strategy sources (name, class_name, hpp, cpp)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.graph.nodes._common import get_llm, last_user_text
from app.graph.state import AgentState
from app.llm.prompts import DESIGN_CODE_SYSTEM
from app.tools.algocraft_client import AlgocraftClient
from app.docs_loader import codegen_context

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


def _template_sources(name: str, class_name: str, idea: str) -> dict[str, str]:
    """Deterministic no-LLM smoke strategy (1-share churn before 15:15 IST)."""
    _ = idea
    hpp = f"""#pragma once

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
}};

}}  // namespace algocraft
"""
    cpp = f"""#include "algocraft/strategies/{name}.hpp"

#include "algocraft/domain/bar_resolution.hpp"
#include "algocraft/domain/session_clock.hpp"
#include "algocraft/strategies/make_intent.hpp"

namespace algocraft {{
namespace {{
constexpr StrategyId kSid = StrategyId::from(9001);
constexpr int kFlattenMin = 15 * 60 + 15;  // 15:15 IST
}}

void {class_name}::configure(const StrategyConfig& config, IndicatorLibrary&) {{
  config_ = config;
}}

void {class_name}::on_bar(const BarEvent& bar, const PortfolioView& pf,
                          std::vector<OrderIntent>& out) {{
  if (bar.symbol_id != config_.symbol_id || bar.resolution != BarResolution::OneMin) {{
    return;
  }}
  const int minute = ist_minute_of_day(bar.timestamp);
  if (minute >= kFlattenMin) {{
    if (pf.position.shares() > 0) {{
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    }}
    return;
  }}
  if (pf.position.shares() > 0) {{
    out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
  }}
  out.push_back(make_intent(kSid, config_.symbol_id, Side::Buy, Quantity{{1}}));
}}

StrategyMetadata {class_name}::metadata() const {{
  return {{"{name}", "1.0.0", TradingMode::Mis, BarResolution::OneMin, {{}}}};
}}

}}  // namespace algocraft
"""
    return {"hpp": hpp, "cpp": cpp}


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
    docs = codegen_context()

    chosen: dict[str, Any]
    if llm is None:
        name = _guess_name(text)
        class_name = snake_to_pascal(name)
        src = _template_sources(name, class_name, text)
        chosen = {
            "name": name,
            "class_name": class_name,
            "kind": "strategy",
            "hpp": src["hpp"],
            "cpp": src["cpp"],
            "source": "template",
        }
    else:
        prompt = (
            f"{DESIGN_CODE_SYSTEM}\n\n"
            f"## C++ docs\n{docs}\n\n"
            f"## User request\n{text}\n\n"
            "Return ONLY JSON with keys: name, class_name, kind, hpp, cpp."
        )
        try:
            resp = await llm.ainvoke(
                [
                    SystemMessage(content=DESIGN_CODE_SYSTEM),
                    HumanMessage(content=prompt),
                ]
            )
            content = resp.content if hasattr(resp, "content") else str(resp)
            data = _parse_codegen_json(str(content))
            name = str(data.get("name") or _guess_name(text)).lower()
            AlgocraftClient.validate_strategy_name(name)
            class_name = str(data.get("class_name") or snake_to_pascal(name))
            hpp = str(data.get("hpp") or "")
            cpp = str(data.get("cpp") or "")
            if not hpp.strip() or not cpp.strip():
                raise ValueError("LLM omitted hpp/cpp")
            chosen = {
                "name": name,
                "class_name": class_name,
                "kind": "strategy",
                "hpp": hpp,
                "cpp": cpp,
                "source": "llm",
            }
        except Exception as exc:  # noqa: BLE001 — fall back to template
            name = _guess_name(text)
            class_name = snake_to_pascal(name)
            src = _template_sources(name, class_name, text)
            chosen = {
                "name": name,
                "class_name": class_name,
                "kind": "strategy",
                "hpp": src["hpp"],
                "cpp": src["cpp"],
                "source": "template_fallback",
                "design_error": str(exc),
            }

    return {
        "chosen": chosen,
        "compile_attempts": 0,
        "max_iterations": state.get("max_iterations") or settings.agent_max_iterations,
        "pending_human": "none",
        "error": None,
    }
