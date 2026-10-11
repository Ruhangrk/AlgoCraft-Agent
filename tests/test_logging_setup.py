"""Logging levels: info < debug < trace."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph.nodes._common import llm_ainvoke, logged_node
from app.logging_setup import (
    TRACE,
    configure_logging,
    format_messages_for_log,
    is_debug_enabled,
    is_trace_enabled,
    level_value,
    normalize_log_level,
)
from app.main import _parse_args


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("info", "info"),
        ("DEBUG", "debug"),
        ("Trace", "trace"),
        ("nope", "info"),
        (None, "info"),
    ],
)
def test_normalize_log_level(raw: str | None, expected: str) -> None:
    assert normalize_log_level(raw) == expected


def test_cli_log_level_flag() -> None:
    assert _parse_args([]).log_level == "info"
    assert _parse_args(["--log-level", "debug"]).log_level == "debug"
    assert _parse_args(["-l", "trace"]).log_level == "trace"
    assert _parse_args(["--port", "9000"]).port == 9000


def test_level_ordering() -> None:
    assert level_value("trace") < level_value("debug") < level_value("info")
    assert TRACE < logging.DEBUG


def test_configure_enables_debug_not_trace(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("debug")
    app_log = logging.getLogger("app")
    assert is_debug_enabled(app_log)
    assert not is_trace_enabled(app_log)
    # Capture everything that is emitted; logger itself still filters TRACE.
    with caplog.at_level(TRACE):
        logging.getLogger("app.test").debug("flow-line")
        logging.getLogger("app.test").log(TRACE, "prompt-line")
    assert "flow-line" in caplog.text
    assert "prompt-line" not in caplog.text


def test_configure_trace_includes_debug(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("trace")
    app_log = logging.getLogger("app")
    assert is_debug_enabled(app_log)
    assert is_trace_enabled(app_log)
    with caplog.at_level(TRACE):
        logging.getLogger("app.test").debug("flow-line")
        logging.getLogger("app.test").log(TRACE, "prompt-line")
    assert "flow-line" in caplog.text
    assert "prompt-line" in caplog.text


def test_format_messages_for_log() -> None:
    text = format_messages_for_log(
        [SystemMessage(content="sys"), HumanMessage(content="hi")]
    )
    assert "role=system" in text
    assert "sys" in text
    assert "hi" in text


@pytest.mark.asyncio
async def test_llm_ainvoke_logs_prompt_at_trace(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("trace")

    class FakeLlm:
        async def ainvoke(self, messages: Any) -> AIMessage:  # noqa: ANN401
            return AIMessage(content='{"intent":"chat"}')

    with caplog.at_level(TRACE, logger="app.llm"):
        resp = await llm_ainvoke(
            FakeLlm(),
            [SystemMessage(content="ROUTE SYS"), HumanMessage(content="hello")],
            label="route",
        )
    assert resp.content == '{"intent":"chat"}'
    assert "ROUTE SYS" in caplog.text
    assert '{"intent":"chat"}' in caplog.text
    assert "[route]" in caplog.text


@pytest.mark.asyncio
async def test_logged_node_emits_debug_flow(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("debug")

    async def sample(state: dict[str, Any], config: Any = None) -> dict[str, Any]:
        _ = config
        return {"intent": "chat", "response_text": "ok"}

    wrapped = logged_node("sample", sample)
    with caplog.at_level(logging.DEBUG, logger="app.graph.nodes.sample"):
        out = await wrapped({"intent": None, "session_id": "s1"})
    assert out["intent"] == "chat"
    assert "→ enter sample" in caplog.text
    assert "← exit sample" in caplog.text
