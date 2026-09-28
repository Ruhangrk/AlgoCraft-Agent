"""In-memory session store (v1)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class Session:
    session_id: str
    user_jwt: str
    provider: str
    model: str
    temperature: float
    workbook_id: int | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_metrics: dict[str, Any] | None = None
    last_card: dict[str, Any] | None = None
    pending_human: str = "none"  # none | promote | activate
    pending_strategy_name: str | None = None
    stream_events: list[dict[str, str]] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    def create(self, session: Session) -> Session:
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def update(self, session: Session) -> Session:
        with self._lock:
            if session.session_id not in self._sessions:
                raise KeyError(session.session_id)
            self._sessions[session.session_id] = session
        return session

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    @staticmethod
    def new_id() -> str:
        return secrets.token_urlsafe(16)


_store = SessionStore()


def get_session_store() -> SessionStore:
    return _store
