"""Async HTTP client for AlgoCraft C++ (:8080)."""

from __future__ import annotations

import re
from typing import Any, Self

import httpx

from app.config import get_settings

_STRATEGY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class AlgocraftApiError(Exception):
    """Non-2xx response from AlgoCraft."""

    def __init__(self, status: int, body: Any) -> None:
        self.status = status
        self.body = body
        super().__init__(f"AlgoCraft API {status}: {body!r}")


class AlgocraftClient:
    def __init__(
        self,
        base_url: str | None = None,
        jwt: str | None = None,
        *,
        timeout_sec: float | None = None,
        long_timeout_sec: float | None = None,
        compile_timeout_sec: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.algocraft_api_url).rstrip("/")
        self._jwt = jwt
        self._timeout = timeout_sec if timeout_sec is not None else settings.agent_http_timeout_sec
        self._long_timeout = (
            long_timeout_sec
            if long_timeout_sec is not None
            else settings.agent_http_long_timeout_sec
        )
        self._compile_timeout = (
            compile_timeout_sec
            if compile_timeout_sec is not None
            else settings.agent_compile_timeout_sec
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self._timeout),
        )

    def with_jwt(self, jwt: str) -> Self:
        """Return a new client sharing timeouts but using `jwt` (never log the token)."""
        clone = type(self)(
            base_url=self.base_url,
            jwt=jwt,
            timeout_sec=self._timeout,
            long_timeout_sec=self._long_timeout,
            compile_timeout_sec=self._compile_timeout,
        )
        return clone

    @property
    def jwt(self) -> str | None:
        return self._jwt

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._jwt:
            headers["Authorization"] = f"Bearer {self._jwt}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        kw: dict[str, Any] = {
            "method": method,
            "url": path,
            "headers": self._headers(),
            "params": params,
            "json": json,
        }
        if timeout is not None:
            kw["timeout"] = timeout
        resp = await self._client.request(**kw)
        try:
            body: Any = resp.json()
        except Exception:
            body = resp.text
        if resp.status_code < 200 or resp.status_code >= 300:
            raise AlgocraftApiError(resp.status_code, body)
        return body

    async def login(self, user: str, password: str) -> str:
        body = await self._request(
            "POST",
            "/auth/login",
            json={"username": user, "password": password},
        )
        if not isinstance(body, dict) or "token" not in body:
            raise AlgocraftApiError(500, body)
        token = str(body["token"])
        self._jwt = token
        return token

    async def list_strategies(self) -> list[str]:
        body = await self._request("GET", "/strategies")
        if not isinstance(body, list):
            raise AlgocraftApiError(500, body)
        return [str(x) for x in body]

    async def list_routers(self) -> list[str]:
        body = await self._request("GET", "/routing-algos")
        if not isinstance(body, list):
            raise AlgocraftApiError(500, body)
        return [str(x) for x in body]

    async def search_instruments(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        body = await self._request(
            "GET",
            "/instruments",
            params={"q": q, "limit": limit},
        )
        if not isinstance(body, list):
            raise AlgocraftApiError(500, body)
        return [dict(x) for x in body]

    async def ensure_market_data(self, body: dict[str, Any]) -> dict[str, Any]:
        raw = await self._request(
            "POST",
            "/market-data/ensure",
            json=body,
            timeout=self._long_timeout,
        )
        if not isinstance(raw, dict):
            raise AlgocraftApiError(500, raw)
        return raw

    async def create_workbook(self, name: str, capital_paise: int) -> int:
        raw = await self._request(
            "POST",
            "/workbooks",
            json={"name": name, "capital_paise": capital_paise},
        )
        if not isinstance(raw, dict) or "id" not in raw:
            raise AlgocraftApiError(500, raw)
        return int(raw["id"])

    async def start_backtest(
        self,
        wid: int,
        *,
        ticker: str,
        strategy: str,
        from_ns: int,
        to_ns: int,
        capital_paise: int,
        **kw: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ticker": ticker,
            "strategy": strategy,
            "from_ns": from_ns,
            "to_ns": to_ns,
            "capital_paise": capital_paise,
            **kw,
        }
        raw = await self._request(
            "POST",
            f"/workbooks/{wid}/backtests/start",
            json=payload,
            timeout=self._long_timeout,
        )
        if not isinstance(raw, dict):
            raise AlgocraftApiError(500, raw)
        return raw

    async def get_backtest(self, wid: int, backtest_id: int) -> dict[str, Any]:
        raw = await self._request("GET", f"/workbooks/{wid}/backtests/{backtest_id}")
        if not isinstance(raw, dict):
            raise AlgocraftApiError(500, raw)
        return raw

    async def start_run(
        self,
        wid: int,
        *,
        router: str,
        capital_paise: int,
        anchor_date: str,
        **kw: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "router": router,
            "capital_paise": capital_paise,
            "anchor_date": anchor_date,
            **kw,
        }
        raw = await self._request(
            "POST",
            f"/workbooks/{wid}/runs/start",
            json=payload,
            timeout=self._long_timeout,
        )
        if not isinstance(raw, dict):
            raise AlgocraftApiError(500, raw)
        return raw

    async def run_events(
        self,
        wid: int,
        rid: int,
        include: str = "routing,fill",
    ) -> list[Any]:
        raw = await self._request(
            "GET",
            f"/workbooks/{wid}/runs/{rid}/events",
            params={"include": include},
        )
        if not isinstance(raw, list):
            raise AlgocraftApiError(500, raw)
        return list(raw)

    @staticmethod
    def validate_strategy_name(name: str) -> str:
        if not _STRATEGY_NAME_RE.match(name):
            raise ValueError(
                f"invalid strategy name {name!r}; expected ^[a-z][a-z0-9_]{{0,63}}$"
            )
        return name

    async def agent_compile(
        self,
        name: str,
        hpp: str,
        cpp: str,
        class_name: str = "",
        *,
        kind: str = "strategy",
    ) -> dict[str, Any]:
        self.validate_strategy_name(name)
        payload = {
            "name": name,
            "class_name": class_name,
            "kind": kind,
            "hpp": hpp,
            "cpp": cpp,
        }
        # 422 = compile failed with log — still raised as AlgocraftApiError(body=...).
        raw = await self._request(
            "POST",
            "/agent/strategies/compile",
            json=payload,
            timeout=self._compile_timeout,
        )
        if not isinstance(raw, dict):
            raise AlgocraftApiError(500, raw)
        return raw

    async def agent_promote(self, name: str) -> dict[str, Any]:
        self.validate_strategy_name(name)
        raw = await self._request(
            "POST",
            "/agent/strategies/promote",
            json={"name": name},
            timeout=self._compile_timeout,
        )
        if not isinstance(raw, dict):
            raise AlgocraftApiError(500, raw)
        return raw

    async def agent_activate(self, name: str, enabled: bool = True) -> dict[str, Any]:
        self.validate_strategy_name(name)
        raw = await self._request(
            "POST",
            "/agent/strategies/activate",
            json={"name": name, "enabled": enabled},
        )
        if not isinstance(raw, dict):
            raise AlgocraftApiError(500, raw)
        return raw

    async def agent_catalog(self) -> list[dict[str, Any]]:
        raw = await self._request("GET", "/agent/strategies/catalog")
        if not isinstance(raw, list):
            raise AlgocraftApiError(500, raw)
        return [dict(x) for x in raw]
