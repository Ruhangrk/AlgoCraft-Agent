"""Validate LLM-emitted AlgoCraft strategy sources before sandbox compile."""

from __future__ import annotations

import re


def validate_strategy_sources(name: str, hpp: str, cpp: str) -> str | None:
    """
    Return an error string if sources are unsafe / fake, else None.

    Catches the common LLM failure mode: inventing a local `class Strategy` and
    stub types so sandbox -fsyntax-only "succeeds" without real AlgoCraft headers.
    """
    if not name or not hpp.strip() or not cpp.strip():
        return "missing name/hpp/cpp"
    if '#include "algocraft/strategies/strategy.hpp"' not in hpp and (
        "#include <algocraft/strategies/strategy.hpp>" not in hpp
    ):
        return 'hpp must #include "algocraft/strategies/strategy.hpp"'
    want = f'#include "algocraft/strategies/{name}.hpp"'
    if want not in cpp:
        return f"cpp must contain {want}"
    if re.search(r"\bclass\s+Strategy\b", hpp) or re.search(r"\bclass\s+Strategy\b", cpp):
        return "do not redefine class Strategy; include the real base header"
    for bad in (
        r"\bstruct\s+Config\b",
        r"\bstruct\s+Bar\b",
        r"\bstruct\s+Metadata\b",
        r"\bplaceholder\b",
        r"\bsubmit\s*\(",
    ):
        if re.search(bad, hpp, re.I) or re.search(bad, cpp, re.I):
            return f"forbidden stub pattern {bad!r}; use real AlgoCraft types / make_intent"
    if re.search(r"Quantity\s*\{\s*\d+", hpp) or re.search(r"Quantity\s*\{\s*\d+", cpp):
        return "use Quantity::from_shares(n); Quantity{n} is private"
    if "final : public Strategy" not in hpp and "final: public Strategy" not in hpp:
        return "hpp class must be `final : public Strategy`"
    # Common LLM mistakes that compile_loop should fix or reject early.
    if "make_intent" in cpp and "make_intent.hpp" not in cpp:
        return 'cpp uses make_intent but missing #include "algocraft/strategies/make_intent.hpp"'
    if "ist_minute_of_day" in cpp and "session_clock.hpp" not in cpp:
        return 'cpp uses ist_minute_of_day but missing #include "algocraft/domain/session_clock.hpp"'
    if "BarResolution::" in cpp and "bar_resolution.hpp" not in cpp and "bar_resolution.hpp" not in hpp:
        return 'cpp uses BarResolution but missing #include "algocraft/domain/bar_resolution.hpp"'
    if re.search(r"\.position\s*\(", cpp):
        return "use pf.position.shares() / pf.position — PortfolioView has no position(symbol)"
    return None


def ensure_required_includes(name: str, cpp: str) -> str:
    """Inject standard AlgoCraft includes after the strategy header include if missing."""
    required = [
        f'#include "algocraft/strategies/{name}.hpp"',
        '#include "algocraft/domain/bar_resolution.hpp"',
        '#include "algocraft/domain/session_clock.hpp"',
        '#include "algocraft/strategies/make_intent.hpp"',
    ]
    text = cpp
    # Ensure strategy header include exists first.
    header = required[0]
    if header not in text:
        text = header + "\n" + text
    insert_at = text.find(header) + len(header)
    for inc in required[1:]:
        if inc not in text:
            text = text[:insert_at] + "\n" + inc + text[insert_at:]
            insert_at = text.find(inc) + len(inc)
    return text


def patch_common_llm_cpp_mistakes(cpp: str) -> str:
    """Fix frequent LLM type mistakes without changing strategy logic."""
    text = cpp
    # OHLC are Price, not double/float.
    text = re.sub(
        r"\b(?:double|float)\s+(\w+)\s*=\s*(bar\.(?:close|open|high|low))\b",
        r"Price \1 = \2",
        text,
    )
    # Literal minute 915 → 15:15 IST
    text = re.sub(r">=\s*915\b", ">= (15 * 60 + 15)", text)
    text = re.sub(r">\s*915\b", "> (15 * 60 + 15)", text)
    return text
