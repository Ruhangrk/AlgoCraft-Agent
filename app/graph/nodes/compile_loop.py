"""Phase B: compile + LLM fix loop (max attempts from settings)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.graph.nodes._common import get_client, get_llm
from app.graph.nodes.design_code import snake_to_pascal
from app.graph.state import AgentState
from app.graph.thinking import thought
from app.llm.prompts import COMPILE_FIX_SYSTEM
from app.tools.algocraft_client import AlgocraftApiError, AlgocraftClient

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


def _parse_fix_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = _JSON_FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("fix JSON must be an object")
    return data


async def _try_compile(client: Any, chosen: dict[str, Any]) -> dict[str, Any]:
    try:
        raw = await client.agent_compile(
            name=str(chosen["name"]),
            hpp=str(chosen["hpp"]),
            cpp=str(chosen["cpp"]),
            class_name=str(chosen.get("class_name") or ""),
            kind=str(chosen.get("kind") or "strategy"),
        )
        return dict(raw) if isinstance(raw, dict) else {"ok": False, "log": str(raw)}
    except AlgocraftApiError as exc:
        body = exc.body if isinstance(exc.body, dict) else {"log": str(exc.body)}
        if exc.status == 422:
            return {**body, "ok": False}
        raise


async def _llm_fix(
    llm: Any,
    *,
    chosen: dict[str, Any],
    log: str,
    attempt: int,
) -> dict[str, Any] | None:
    prompt = (
        f"Attempt {attempt}. Fix the strategy so it compiles.\n"
        f"name={chosen.get('name')} class_name={chosen.get('class_name')}\n\n"
        f"## Compiler log\n{log[-8000:]}\n\n"
        f"## Current hpp\n```cpp\n{chosen.get('hpp')}\n```\n\n"
        f"## Current cpp\n```cpp\n{chosen.get('cpp')}\n```\n\n"
        "Return ONLY JSON with keys: hpp, cpp (optional name, class_name)."
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=COMPILE_FIX_SYSTEM), HumanMessage(content=prompt)]
    )
    content = resp.content if hasattr(resp, "content") else str(resp)
    try:
        return _parse_fix_json(str(content))
    except Exception:  # noqa: BLE001
        return None


def _with_thoughts(base: dict[str, Any], crumbs: list[dict[str, Any]]) -> dict[str, Any]:
    return {**base, "thinking": crumbs}


async def compile_loop(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    client = get_client(config)
    llm = get_llm(config)
    settings = get_settings()
    max_attempts = settings.agent_max_compile_attempts
    chosen = dict(state.get("chosen") or {})
    crumbs: list[dict[str, Any]] = []

    def note(text: str, *, phase: str = "tool", data: dict[str, Any] | None = None) -> None:
        crumbs.extend(thought("compile_loop", text, phase=phase, data=data)["thinking"])

    if not chosen.get("name") or not chosen.get("hpp") or not chosen.get("cpp"):
        return {
            "error": "compile_loop: missing chosen name/hpp/cpp",
            "eval_verdict": "error",
            "pending_human": "none",
            "cpp_results": {},
        }

    try:
        AlgocraftClient.validate_strategy_name(str(chosen["name"]))
    except ValueError as exc:
        note(str(exc), phase="result")
        return _with_thoughts(
            {
                "error": str(exc),
                "eval_verdict": "error",
                "pending_human": "none",
                "cpp_results": {},
            },
            crumbs,
        )

    attempts = int(state.get("compile_attempts") or 0)
    last: dict[str, Any] = {}
    note(
        f"Starting compile loop for `{chosen['name']}` (max {max_attempts} attempts).",
        phase="start",
        data={"name": chosen["name"], "max_attempts": max_attempts},
    )

    while attempts < max_attempts:
        attempts += 1
        note(f"Compile attempt {attempts}/{max_attempts} → POST /agent/strategies/compile")
        try:
            last = await _try_compile(client, chosen)
        except Exception as exc:  # noqa: BLE001
            note(f"Compile request failed: {exc}", phase="result")
            return _with_thoughts(
                {
                    "chosen": chosen,
                    "compile_attempts": attempts,
                    "cpp_results": {"ok": False, "error": str(exc)},
                    "eval_verdict": "error",
                    "pending_human": "none",
                    "error": f"compile request failed: {exc}",
                    "feedback": str(exc),
                },
                crumbs,
            )

        if last.get("ok") is True:
            note(
                f"Compile OK after {attempts} attempt(s). pending_human=promote "
                f"(sandbox={last.get('sandbox_dir')}).",
                phase="result",
                data={"ok": True, "attempts": attempts},
            )
            draft = dict(state.get("create_draft") or {})
            if draft:
                draft = {**draft, "status": "compiled", "active": True, "name": chosen["name"]}
            return _with_thoughts(
                {
                    "chosen": chosen,
                    "create_draft": draft or state.get("create_draft"),
                    "compile_attempts": attempts,
                    "cpp_results": last,
                    "eval_verdict": "need_human",
                    "pending_human": "promote",
                    "error": None,
                    "feedback": (
                        f"Compile ok for `{chosen['name']}` after {attempts} attempt(s). "
                        "Await human confirm before promote."
                    ),
                    "metrics": {
                        "compile_ok": True,
                        "compile_attempts": attempts,
                        "name": chosen["name"],
                        "sandbox_dir": last.get("sandbox_dir"),
                    },
                },
                crumbs,
            )

        log = str(last.get("log") or last.get("error") or "compile failed")
        note(
            f"Compile failed attempt {attempts}: {log[:400]}",
            phase="result",
            data={"ok": False, "attempts": attempts},
        )
        if llm is None or attempts >= max_attempts:
            if llm is None:
                note("No LLM injected — cannot auto-fix; stopping.", phase="decide")
            break

        note(f"Asking LLM to fix sources from compiler log (attempt {attempts}).", phase="decide")
        fixed = await _llm_fix(llm, chosen=chosen, log=log, attempt=attempts)
        if not fixed:
            note("LLM fix parse failed — stopping.", phase="result")
            break
        if fixed.get("hpp"):
            chosen["hpp"] = str(fixed["hpp"])
        if fixed.get("cpp"):
            chosen["cpp"] = str(fixed["cpp"])
        if fixed.get("name"):
            try:
                name = AlgocraftClient.validate_strategy_name(str(fixed["name"]).lower())
                chosen["name"] = name
                if not fixed.get("class_name"):
                    chosen["class_name"] = snake_to_pascal(name)
            except ValueError:
                pass
        if fixed.get("class_name"):
            chosen["class_name"] = str(fixed["class_name"])
        note("Applied LLM fix; will recompile.", phase="decide")

    log = str(last.get("log") or "compile failed")
    note(f"Giving up after {attempts} attempt(s).", phase="result")
    return _with_thoughts(
        {
            "chosen": chosen,
            "compile_attempts": attempts,
            "cpp_results": last or {"ok": False, "log": log},
            "eval_verdict": "error",
            "pending_human": "none",
            "error": f"compile failed after {attempts} attempt(s)",
            "feedback": log[-2000:],
            "metrics": {
                "compile_ok": False,
                "compile_attempts": attempts,
                "name": chosen.get("name"),
            },
        },
        crumbs,
    )
