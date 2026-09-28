"""Session routes: create / get / patch LLM prefs."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.llm.catalog import load_catalog
from app.models.api import (
    CreateSessionRequest,
    PatchLlmRequest,
    SessionDetailOut,
    SessionLlmOut,
)
from app.store.sessions import Session, get_session_store

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


def _bearer_jwt(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization Bearer JWT required")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Authorization Bearer JWT required")
    return parts[1].strip()


def _resolve_llm(
    *,
    provider: str | None,
    model: str | None,
    temperature: float | None,
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
    fallback_temperature: float | None = None,
) -> tuple[str, str, float]:
    catalog = load_catalog()
    defaults = catalog.defaults()
    prov = provider or fallback_provider or defaults[0]
    mod = model or fallback_model or defaults[1]
    temp_in = (
        temperature
        if temperature is not None
        else (fallback_temperature if fallback_temperature is not None else defaults[2])
    )
    try:
        catalog.resolve(prov, mod)
        temp = catalog.clamp_temperature(temp_in)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return prov, mod, temp


def _session_detail(session: Session) -> SessionDetailOut:
    return SessionDetailOut(
        session_id=session.session_id,
        provider=session.provider,
        model=session.model,
        temperature=session.temperature,
        workbook_id=session.workbook_id,
        messages=list(session.messages),
        last_metrics=session.last_metrics,
        last_card=session.last_card,
        pending_human=session.pending_human,  # type: ignore[arg-type]
    )


@router.post("", response_model=SessionLlmOut, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    authorization: str | None = Header(default=None),
) -> SessionLlmOut:
    jwt = _bearer_jwt(authorization)
    provider, model, temperature = _resolve_llm(
        provider=body.provider,
        model=body.model,
        temperature=body.temperature,
    )
    store = get_session_store()
    session = Session(
        session_id=store.new_id(),
        user_jwt=jwt,
        provider=provider,
        model=model,
        temperature=temperature,
        workbook_id=body.workbook_id,
    )
    store.create(session)
    return SessionLlmOut(
        session_id=session.session_id,
        provider=session.provider,
        model=session.model,
        temperature=session.temperature,
        workbook_id=session.workbook_id,
    )


@router.get("/{session_id}", response_model=SessionDetailOut)
async def get_session(session_id: str) -> SessionDetailOut:
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_detail(session)


@router.patch("/{session_id}/llm", response_model=SessionLlmOut)
async def patch_session_llm(session_id: str, body: PatchLlmRequest) -> SessionLlmOut:
    store = get_session_store()
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    provider, model, temperature = _resolve_llm(
        provider=body.provider,
        model=body.model,
        temperature=body.temperature,
        fallback_provider=session.provider,
        fallback_model=session.model,
        fallback_temperature=session.temperature,
    )
    session.provider = provider
    session.model = model
    session.temperature = temperature
    store.update(session)
    return SessionLlmOut(
        session_id=session.session_id,
        provider=session.provider,
        model=session.model,
        temperature=session.temperature,
        workbook_id=session.workbook_id,
    )
