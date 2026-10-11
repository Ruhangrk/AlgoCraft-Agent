"""Validate strategy source guards + pattern templates."""

from __future__ import annotations

from app.graph.nodes.design_code import _detect_pattern, _template_sources, snake_to_pascal
from app.graph.nodes.strategy_sources import validate_strategy_sources


def test_rejects_fake_strategy_base() -> None:
    hpp = """
#pragma once
namespace algocraft {
class Strategy { virtual void on_bar() = 0; };
class Foo final : public Strategy {};
}
"""
    assert validate_strategy_sources("foo", hpp, '#include "algocraft/strategies/foo.hpp"\n')


def test_accepts_real_shape() -> None:
    src, pattern = _template_sources("agent_ok_two_red", "AgentOkTwoRed", "2 consecutive red then green")
    assert pattern == "two_red"
    assert validate_strategy_sources("agent_ok_two_red", src["hpp"], src["cpp"]) is None


def test_pattern_detection() -> None:
    assert _detect_pattern("buy after 2 consecutive green bars, sell red") == "two_green"
    assert _detect_pattern("open clip after 09:20 IST single clip") == "open_clip"
    assert _detect_pattern("something exotic with RSI") == "churn"


def test_pascal() -> None:
    assert snake_to_pascal("agent_ok_two_red") == "AgentOkTwoRed"
