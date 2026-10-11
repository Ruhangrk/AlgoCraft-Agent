"""Application logging: info < debug < trace.

- info:  operational / standard logs (API turns, errors)
- debug: info + graph node enter/exit (function-to-function flow)
- trace: debug + LLM prompts/responses and C++ HTTP detail
"""

from __future__ import annotations

import logging
import sys
from typing import Any

# More verbose than DEBUG (10). Shown only when AGENT_LOG_LEVEL=trace.
TRACE = 5
logging.addLevelName(TRACE, "TRACE")

_LEVEL_MAP = {
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "trace": TRACE,
}

def normalize_log_level(name: str | None) -> str:
    key = (name or "info").strip().lower()
    return key if key in _LEVEL_MAP else "info"


def level_value(name: str | None) -> int:
    return _LEVEL_MAP[normalize_log_level(name)]


def configure_logging(level_name: str | None = None) -> None:
    """Idempotent root + app logger setup from AGENT_LOG_LEVEL."""
    level = level_value(level_name)

    root = logging.getLogger()
    root.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        handler.setLevel(level)
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            handler.setLevel(min(handler.level, level) if handler.level else level)

    logging.getLogger("app").setLevel(level)

    # Keep third-party noise down; our own TRACE covers HTTP when needed.
    for name in ("httpx", "httpcore", "openai", "urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def is_debug_enabled(logger: logging.Logger | None = None) -> bool:
    log = logger or logging.getLogger("app")
    return log.isEnabledFor(logging.DEBUG)


def is_trace_enabled(logger: logging.Logger | None = None) -> bool:
    log = logger or logging.getLogger("app")
    return log.isEnabledFor(TRACE)


def log_trace(logger: logging.Logger, msg: str, *args: Any, **kwargs: Any) -> None:
    logger.log(TRACE, msg, *args, **kwargs)


def format_messages_for_log(messages: Any) -> str:
    """Pretty-print LangChain-style message list for TRACE."""
    if messages is None:
        return "<none>"
    lines: list[str] = []
    try:
        seq = list(messages)
    except TypeError:
        return repr(messages)
    for i, msg in enumerate(seq):
        role = getattr(msg, "type", None) or getattr(msg, "role", None) or type(msg).__name__
        content = getattr(msg, "content", msg)
        if not isinstance(content, str):
            content = str(content)
        lines.append(f"--- message[{i}] role={role} ({len(content)} chars) ---")
        lines.append(content)
    return "\n".join(lines) if lines else "<empty>"


def truncate_for_log(text: str, limit: int = 120_000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [truncated, {len(text) - limit} more chars]"
