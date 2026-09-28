"""Phase C confirm / promote / activate tests (mocked C++ client)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.store.sessions import Session, get_session_store
from app.tools.algocraft_client import AlgocraftApiError


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    get_session_store().clear()
    yield
    get_session_store().clear()


def _seed_pending(action: str = "promote", name: str = "my_mean_revert") -> Session:
    store = get_session_store()
    session = Session(
        session_id=store.new_id(),
        user_jwt="test-jwt",
        provider="groq",
        model="openai/gpt-oss-20b",
        temperature=0.2,
        pending_human=action,
        pending_strategy_name=name,
        last_card={"strategy_name": name, "pending_human": action},
    )
    store.create(session)
    return session


class FakeLifecycleClient:
    def __init__(self) -> None:
        self.promotes: list[str] = []
        self.activates: list[tuple[str, bool]] = []

    async def agent_promote(self, name: str) -> dict:
        self.promotes.append(name)
        return {
            "ok": True,
            "id": 42,
            "name": name,
            "class_name": "MyMeanRevert",
            "enabled": False,
            "hpp_path": f"include/algocraft/strategies/{name}.hpp",
            "cpp_path": f"src/strategies/{name}.cpp",
            "note": "promoted enabled=0",
        }

    async def agent_activate(self, name: str, enabled: bool = True) -> dict:
        self.activates.append((name, enabled))
        return {
            "ok": True,
            "id": 42,
            "name": name,
            "enabled": enabled,
            "note": "rebuild+restart required",
        }

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_confirm_promote_then_activate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _seed_pending("promote")
    fake = FakeLifecycleClient()

    async def _run(**kwargs):  # noqa: ANN003
        from app.graph.lifecycle import run_confirm as real

        return await real(client=fake, **kwargs)

    monkeypatch.setattr("app.api.confirm.run_confirm", _run)

    r1 = client.post(f"/v1/sessions/{session.session_id}/confirm", json={"action": "promote"})
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["pending_human"] == "activate"
    assert body1["verdict"] == "need_human"
    assert "Promoted" in (body1["response_text"] or "")
    assert fake.promotes == ["my_mean_revert"]

    detail = client.get(f"/v1/sessions/{session.session_id}").json()
    assert detail["pending_human"] == "activate"
    assert detail["pending_strategy_name"] == "my_mean_revert"

    r2 = client.post(f"/v1/sessions/{session.session_id}/confirm", json={"action": "activate"})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["pending_human"] == "none"
    assert body2["verdict"] == "pass"
    assert fake.activates == [("my_mean_revert", True)]
    assert "Activated" in (body2["response_text"] or "") or "rebuild" in (
        body2["response_text"] or ""
    ).lower()

    detail2 = client.get(f"/v1/sessions/{session.session_id}").json()
    assert detail2["pending_human"] == "none"
    assert detail2["pending_strategy_name"] is None


def test_confirm_wrong_gate_409(client: TestClient) -> None:
    session = _seed_pending("promote")
    resp = client.post(
        f"/v1/sessions/{session.session_id}/confirm", json={"action": "activate"}
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["pending_human"] == "promote"


def test_confirm_missing_session(client: TestClient) -> None:
    resp = client.post("/v1/sessions/nope/confirm", json={"action": "promote"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_approve_promote(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _seed_pending("promote")
    fake = FakeLifecycleClient()

    async def _run(**kwargs):  # noqa: ANN003
        from app.graph.lifecycle import run_confirm as real

        return await real(client=fake, **kwargs)

    monkeypatch.setattr("app.api.chat.run_confirm", _run)

    chat = client.post(
        "/v1/chat",
        json={"session_id": session.session_id, "message": "APPROVE_PROMOTE"},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["verdict"] == "need_human"
    assert get_session_store().get(session.session_id).pending_human == "activate"


@pytest.mark.asyncio
async def test_promote_node_direct() -> None:
    from app.graph.nodes.promote import promote

    fake = FakeLifecycleClient()
    out = await promote(
        {
            "pending_human": "promote",
            "chosen": {"name": "my_mean_revert"},
        },
        {"configurable": {"algocraft": fake}},
    )
    assert out["pending_human"] == "activate"
    assert out["metrics"]["promoted"] is True


@pytest.mark.asyncio
async def test_human_gate_rejects_mismatch() -> None:
    from app.graph.nodes.human_gate import human_gate

    out = await human_gate(
        {"pending_human": "promote", "chosen": {"name": "x"}},
        {"configurable": {"confirm_action": "activate"}},
    )
    assert out["eval_verdict"] == "error"
    assert "expected pending_human" in (out.get("error") or "")


@pytest.mark.asyncio
async def test_promote_cpp_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.graph.nodes.promote import promote

    class Boom:
        async def agent_promote(self, name: str) -> dict:
            raise AlgocraftApiError(500, {"error": "disk full"})

    out = await promote(
        {"pending_human": "promote", "chosen": {"name": "my_mean_revert"}},
        {"configurable": {"algocraft": Boom()}},
    )
    assert out["eval_verdict"] == "error"
    assert out["pending_human"] == "promote"
