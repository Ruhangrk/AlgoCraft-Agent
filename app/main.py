"""FastAPI entrypoint."""

from __future__ import annotations

import argparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, confirm, health, llm_catalog, sessions
from app.config import get_settings
from app.logging_setup import configure_logging, get_logger, normalize_log_level

settings = get_settings()
# Import-time default (tests / `uvicorn app.main:app`). CLI overrides in main().
configure_logging(settings.agent_log_level)
log = get_logger("app.main")

app = FastAPI(title="AlgoCraft-Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(llm_catalog.router)
app.include_router(sessions.router)
app.include_router(confirm.router)
app.include_router(chat.router)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="algocraft-agent",
        description="AlgoCraft-Agent — FastAPI + LangGraph strategy agent",
    )
    p.add_argument(
        "--log-level",
        "-l",
        choices=("info", "debug", "trace"),
        default="info",
        help=(
            "Logging verbosity (default: info). "
            "debug = graph node flow; trace = LLM prompts/responses + C++ HTTP"
        ),
    )
    p.add_argument(
        "--host",
        default=settings.agent_host,
        help=f"Bind host (default: {settings.agent_host})",
    )
    p.add_argument(
        "--port",
        type=int,
        default=settings.agent_port,
        help=f"Bind port (default: {settings.agent_port})",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    args = _parse_args(argv)
    log_level = normalize_log_level(args.log_level)
    configure_logging(log_level)
    log.info(
        "AlgoCraft-Agent starting host=%s port=%s log_level=%s",
        args.host,
        args.port,
        log_level,
    )

    uv_level = "debug" if log_level in ("debug", "trace") else "info"
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level=uv_level,
    )


if __name__ == "__main__":
    main()
