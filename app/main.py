"""FastAPI entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, confirm, health, llm_catalog, sessions
from app.config import get_settings

settings = get_settings()

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


def main() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.agent_host,
        port=settings.agent_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
