"""Shared helpers for graph nodes."""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState
from app.logging_setup import (
    format_messages_for_log,
    get_logger,
    is_trace_enabled,
    log_trace,
    truncate_for_log,
)
from app.tools.algocraft_client import AlgocraftClient

F = TypeVar("F", bound=Callable[..., Any])


def llm_content_text(content: Any) -> str:
    """Normalize chat-model content (str | list blocks) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            else:
                text = getattr(block, "text", None)
                parts.append(str(text if text is not None else block))
        return "".join(parts).strip()
    return str(content).strip()


def last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, BaseMessage) and msg.type == "human":
            return str(msg.content)
        if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return str(msg.get("content", ""))
        if isinstance(msg, dict) and msg.get("type") == "human":
            return str(msg.get("content", ""))
    return ""


def configurable(config: RunnableConfig | None) -> dict[str, Any]:
    return dict((config or {}).get("configurable") or {})


def get_llm(config: RunnableConfig | None) -> BaseChatModel | None:
    llm = configurable(config).get("llm")
    return cast(BaseChatModel | None, llm)


def get_client(config: RunnableConfig | None) -> AlgocraftClient:
    client = configurable(config).get("algocraft")
    if client is None:
        raise RuntimeError("configurable['algocraft'] client required")
    # Duck-typed test fakes are allowed at runtime; cast keeps IDE/refs honest.
    return cast(AlgocraftClient, client)


def _state_flow_summary(state: AgentState | dict[str, Any]) -> str:
    keys = (
        "intent",
        "session_id",
        "iteration",
        "compile_attempts",
        "create_ready",
        "eval_verdict",
        "pending_human",
        "error",
    )
    parts = [f"{k}={state.get(k)!r}" for k in keys if state.get(k) not in (None, "", {})]
    chosen = state.get("chosen") or {}
    if isinstance(chosen, dict) and chosen.get("name"):
        parts.append(f"chosen={chosen.get('name')!r}")
    return " ".join(parts) if parts else "(no key state)"


def _result_flow_summary(result: Any) -> str:
    if not isinstance(result, dict):
        return type(result).__name__
    interesting = (
        "intent",
        "create_ready",
        "eval_verdict",
        "pending_human",
        "error",
        "response_text",
    )
    parts: list[str] = []
    for k in interesting:
        if k not in result:
            continue
        val = result[k]
        if k == "response_text" and isinstance(val, str):
            parts.append(f"response_text={len(val)}chars")
        elif val not in (None, "", {}):
            parts.append(f"{k}={val!r}")
    chosen = result.get("chosen") or {}
    if isinstance(chosen, dict) and chosen.get("name"):
        parts.append(f"chosen={chosen.get('name')!r}")
    parts.append(f"keys={sorted(result.keys())}")
    return " ".join(parts)


def logged_node(name: str, fn: F) -> F:
    """Wrap a graph node with DEBUG enter/exit flow logs."""
    log = get_logger(f"app.graph.nodes.{name}")

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            state = cast(AgentState, args[0] if args else kwargs.get("state") or {})
            log.debug("→ enter %s | %s", name, _state_flow_summary(state))
            t0 = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
            except Exception:
                log.exception("✗ fail %s after %.0fms", name, (time.perf_counter() - t0) * 1000)
                raise
            log.debug(
                "← exit %s (%.0fms) | %s",
                name,
                (time.perf_counter() - t0) * 1000,
                _result_flow_summary(result),
            )
            return result

        return cast(F, _async_wrapper)

    @functools.wraps(fn)
    def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        state = cast(AgentState, args[0] if args else kwargs.get("state") or {})
        log.debug("→ enter %s | %s", name, _state_flow_summary(state))
        t0 = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except Exception:
            log.exception("✗ fail %s after %.0fms", name, (time.perf_counter() - t0) * 1000)
            raise
        log.debug(
            "← exit %s (%.0fms) | %s",
            name,
            (time.perf_counter() - t0) * 1000,
            _result_flow_summary(result),
        )
        return result

    return cast(F, _sync_wrapper)


async def llm_ainvoke(
    llm: Any,
    messages: Any,
    *,
    label: str,
) -> Any:
    """Invoke chat model; TRACE logs full prompt + response."""
    log = get_logger("app.llm")
    if is_trace_enabled(log):
        log_trace(
            log,
            "[%s] prompt\n%s",
            label,
            truncate_for_log(format_messages_for_log(messages)),
        )
    t0 = time.perf_counter()
    try:
        resp = await llm.ainvoke(messages)
    except Exception:
        log.exception("[%s] LLM invoke failed after %.0fms", label, (time.perf_counter() - t0) * 1000)
        raise
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if is_trace_enabled(log):
        content = llm_content_text(getattr(resp, "content", resp))
        meta = dict(getattr(resp, "response_metadata", None) or {})
        usage = getattr(resp, "usage_metadata", None)
        log_trace(
            log,
            "[%s] response (%.0fms) meta=%s usage=%s\n%s",
            label,
            elapsed_ms,
            meta,
            usage,
            truncate_for_log(content),
        )
    else:
        log.debug("[%s] LLM ok (%.0fms)", label, elapsed_ms)
    return resp
