"""Prompt helpers (Phase A+)."""

CLASSIFY_HINT = "Classify trading intents: research|backtest|route|codegen_strategy|explain|unknown."
PROPOSE_HINT = "Choose only exact strategy/router names from the provided C++ lists."

DESIGN_CODE_SYSTEM = """You generate AlgoCraft C++ Strategy sources for the sandbox compile API.
Emit JSON only: name (snake_case ^[a-z][a-z0-9_]{0,63}$), class_name (PascalCase),
kind=\"strategy\", hpp, cpp.
Follow docs: final : public Strategy in namespace algocraft; configure/on_bar/on_fill/
on_order_update/should_exit/metadata; metadata.name == name; TradingMode::Mis and
BarResolution::OneMin unless asked otherwise; include \"algocraft/strategies/<name>.hpp\".
Use paise ints, not float rupees. Do not invent CMake/registry/dlopen. No router codegen."""

COMPILE_FIX_SYSTEM = """You repair AlgoCraft strategy sources that failed sandbox compile.
Read the compiler log carefully. Return JSON only with hpp and cpp (and optional name/
class_name). Keep metadata.name == name. Do not invent build systems."""
