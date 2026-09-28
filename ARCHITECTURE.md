# AlgoCraft-Agent — Build Spec (for implementers / Cursor)

**Repo to create:** `AlgoCraft-Agent` (sibling of `AlgoCraft`)  
**Stack:** Python 3.11+ · **uv** · FastAPI · LangGraph · httpx · Pydantic v2 · SSE  
**Canonical docs:** keep `Notes/AI_AGENT.md` and root `ARCHITECTURE.md` in sync.

**Status (2026-09-28):**
- C++ engine APIs for Phase A **and** B/C compile/promote/activate are **implemented** in AlgoCraft.
- Python agent code: **not started**. This doc is the full build plan.
- **LLM:** multi-provider YAML allowlist ∩ live discovery; rate-limit → user switches; DeepSeek last; mock while coding (§8). Locked.

**Non-goals (v1):** auto live trading without human approval; LLM shell/git access; embedding bars/risk in Python; arbitrary client-supplied model ids / base URLs.

---

## 0. How to use this doc (Cursor cascade)

Build **in order**. Do not skip Phase A for B/C.

1. Create repo + skeleton (§7, §12 step 1–3) — includes LLM catalog/factory  
2. `AlgocraftClient` against live `:8080` (§6, §9)  
3. LangGraph Phase A with mocks, then real tools (§4, §12)  
4. FastAPI chat + SSE (§5)  
5. Phase B compile loop (§4.5, §6.2)  
6. Phase C promote/activate with **human confirmation tool** (§4.6, §6.2)  

**Prereq:** AlgoCraft `scripts/serve` running; user registered; JWT works. User has filled `AGENT_SECRETS_FILE` for at least one LLM provider.

---

## 1. Purpose

Chat orchestrator that:

1. Parses a trading idea  
2. Researches via C++ HTTP (`/instruments`, `/strategies`, `/routing-algos`)  
3. Proposes an existing strategy/router **or** (Phase B) generates C++ sources  
4. Runs **real** backtests / hist runs on AlgoCraft  
5. Evaluates metrics (soft thresholds)  
6. Asks human before promote/activate  

Python = brain + HTTP tools. C++ = capital, bars, fills, risk, compile sandbox.

---

## 2. Placement

```
AlgoCraft-UI (:5173)
    ├── JWT ──► AlgoCraft C++ (:8080)
    └── JWT ──► AlgoCraft-Agent (:8100)
                    └── httpx + Bearer ──► AlgoCraft C++ (:8080)
```

| Rule | Locked decision |
|------|-----------------|
| Auth to C++ | **Forward the end-user JWT** from UI→Agent→C++ (`Authorization: Bearer …`). Fallback: login as `ALGOCRAFT_USER` / `ALGOCRAFT_PASS` only for CLI smoke. |
| Workbook | Session may include `workbook_id`; else `POST /workbooks` once and store id. |
| Default run mode | **Hist** with past `anchor_date` (not live today) unless user explicitly asks live. |
| Tool timeout | **600s** for `runs/start` / heavy backtests; **120s** for light GETs; compile **180s**. |
| Eval | Soft verdict (pass/fail/weak) — do **not** hard-stop only because `pnl <= 0`. |
| Concurrency | 1 uvicorn worker; max 2 concurrent graphs. |

---

## 3. Phases

### Phase A — Chat + existing strategies (ship first)
- No codegen. Pick from `GET /strategies` / `GET /routing-algos`.
- Tools: auth, list, instruments, ensure, workbook, backtest, hist run, events.

### Phase B — Codegen + compile loop
- LLM emits `name` (snake_case), `hpp`, `cpp` matching AlgoCraft `Strategy` API.
- Tool: `POST /agent/strategies/compile` until `ok=true` (max compile attempts = 5).
- **Do not** promote without human OK.

### Phase C — Promote + activate
- Human OK → `POST /agent/strategies/promote` (`enabled=0` in catalog).
- Second human OK → `POST /agent/strategies/activate` (`enabled=1`).
- Tell user: **rebuild + `scripts/serve --restart`** required for new C++ to load into the in-process registry (no dlopen yet).

---

## 4. LangGraph

### 4.1 Phase A graph

```
START → classify_intent → research → propose → execute → evaluate
                              ↑                      │
                              └──── iterate < max ────┘ (verdict=fail/weak)
                                                    │
                                                    ▼
                                                 respond → END
```

Use `langgraph.graph.StateGraph`. Conditional edges from `evaluate`:
- `pass` | `need_human` → `respond`
- `fail` / `weak` and `iteration < max_iterations` → `propose` (increment `iteration`, set `feedback`)
- else → `respond`

### 4.2 Phase B/C extension (same graph, extra intent)

If intent = `codegen_strategy`:

```
research → design_code → compile_loop → (human_gate_promote) → promote
        → (human_gate_activate) → activate → respond
```

`compile_loop`: call compile; if not ok, LLM fixes from `log`; repeat ≤ 5.

### 4.3 AgentState (Pydantic preferred)

```python
from typing import Annotated, Any, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    session_id: str
    user_jwt: str                    # forwarded to C++
    workbook_id: int | None
    # LLM selection lives on the session + LangGraph configurable — NOT api keys
    llm_provider: str                # e.g. "deepseek" | "gemini" | "openrouter" | "groq"
    llm_model: str                   # exact allowlisted model id for that provider
    llm_temperature: float           # from UI; clamped to catalog [min, max]

    intent: Literal[
        "research", "backtest", "route", "codegen_strategy", "explain", "unknown"
    ]
    tickers: list[str]
    strategy_candidates: list[str]
    router_candidates: list[str]
    research_notes: str

    chosen: dict[str, Any]
    # backtest: {strategy, ticker, from_ns, to_ns, capital_paise}
    # route:    {router, anchor_date, capital_paise}  # hist preferred
    # codegen:  {name, class_name, hpp, cpp}

    cpp_results: dict[str, Any]
    metrics: dict[str, Any]
    eval_verdict: Literal["pass", "weak", "fail", "need_human", "error"]
    feedback: str
    iteration: int
    max_iterations: int              # default 3
    compile_attempts: int            # default 0, max 5
    pending_human: Literal["none", "promote", "activate"]
    error: str | None
```

### 4.4 Node contracts (implement these files)

| Node | File | Must do |
|------|------|---------|
| `classify_intent` | `nodes/classify.py` | LLM or rules → `intent` |
| `research` | `nodes/research.py` | `list_strategies`, `list_routers`, optional `search_instruments`, `ensure_market_data` |
| `propose` | `nodes/propose.py` | LLM constrained to **exact** names from C++; fill `chosen` |
| `execute` | `nodes/execute.py` | `start_backtest` **or** `start_run` (hist); store raw JSON in `cpp_results` |
| `evaluate` | `nodes/evaluate.py` | Pure Python thresholds → `eval_verdict`, `metrics`, `feedback` |
| `respond` | `nodes/respond.py` | LLM summary + structured `card` JSON for UI |
| `design_code` | `nodes/design_code.py` | Phase B: emit Strategy sources |
| `compile_loop` | `nodes/compile_loop.py` | Phase B: compile + fix |
| `human_gate` | `nodes/human_gate.py` | Interrupt / wait for UI `confirm=true` before promote/activate |

**LLM injection:** nodes that need a model read `config["configurable"]["llm"]` (a LangChain `BaseChatModel` built by `get_chat_model`). Do **not** branch on provider inside nodes. Do **not** put API keys in `AgentState`.

### 4.5 Evaluate thresholds (env)

```text
AGENT_MAX_ITERATIONS=3
AGENT_MIN_FILLS=2
AGENT_MAX_FILLS=5000
AGENT_SOFT_MIN_PNL_PAISE=1      # pnl >= this → "pass"; else if fills ok → "weak"; else "fail"
```

Logic sketch:
```python
fills = metrics.get("fills", 0)
pnl = metrics.get("pnl_paise", 0)
if fills < min_fills:
    verdict = "fail"
elif pnl >= soft_min_pnl:
    verdict = "pass"
else:
    verdict = "weak"   # still show results; allow iterate
```

### 4.6 Human gates (Phase C)

Do **not** auto-promote. Patterns:
- LangGraph `interrupt()` / wait for next chat message `APPROVE_PROMOTE` / `APPROVE_ACTIVATE`, **or**
- FastAPI `POST /v1/sessions/{id}/confirm` with `{action: "promote"|"activate"}`.

Agent message must show: strategy name, compile log summary, paths, risk note (restart required).

---

## 5. FastAPI surface (Python)

| Method | Path | Body / notes |
|--------|------|----------------|
| `GET` | `/healthz` | `{status, cpp_reachable}` |
| `GET` | `/v1/llm/catalog` | Allowlisted providers + models for UI dropdowns (**no API keys**). Marks `available` if that provider’s env key is set. |
| `POST` | `/v1/sessions` | `{workbook_id?, provider?, model?, temperature?}` + header `Authorization` (user JWT) → `{session_id, provider, model, temperature}`. Missing fields → catalog defaults. Validate allowlist + temp range. |
| `PATCH` | `/v1/sessions/{id}/llm` | `{provider?, model?, temperature?}` — change dropdowns / temp mid-session; re-validate. |
| `GET` | `/v1/sessions/{id}` | history + last metrics/card + current `provider`/`model`/`temperature` |
| `POST` | `/v1/chat` | `{session_id, message, provider?, model?, temperature?}` — optional override for this turn; else session defaults. Runs graph (sync JSON) **or** kicks async job |
| `GET` | `/v1/chat/{session_id}/stream` | **SSE**: `event: token\|tool\|card\|error\|done` — `error` includes `llm_rate_limited` (§8.8) |
| `POST` | `/v1/sessions/{id}/confirm` | `{action: "promote"\|"activate"}` |

Sessions: **in-memory dict** v1 (`SessionStore`); optional SQLite later.  
CORS: allow `http://127.0.0.1:5173`.

**UI contract:** two dropdowns (provider → models) **plus a temperature control** (slider or number) bound to catalog `temperature_min`/`temperature_max`/`default_temperature`. Never free-text model ids.

---

## 6. C++ HTTP contracts (exact)

Base: `ALGOCRAFT_API_URL` default `http://127.0.0.1:8080`.  
All mutating/agent routes need `Authorization: Bearer <jwt>` except `/auth/login` and `/auth/register`.

### 6.1 Phase A tools

| Tool | Request | Response highlights |
|------|---------|---------------------|
| `login` | `POST /auth/login` `{"username","password"}` | `{token}` or equivalent — store JWT |
| `list_strategies` | `GET /strategies` | list/array of names |
| `list_routers` | `GET /routing-algos` | includes `default_router`, `top15_week_router`, `live_run_testing_router` |
| `search_instruments` | `GET /instruments?q=ONGC&limit=20` | rows with ticker |
| `ensure_market_data` | `POST /market-data/ensure` body per UI (tickers + range) | results |
| `create_workbook` | `POST /workbooks` `{"name","capital_paise"}` | `{id}` |
| `start_backtest` | `POST /workbooks/{wid}/backtests/start` | **required:** `ticker`, `strategy`, `from_ns`, `to_ns`, `capital_paise`; optional `order_qty`, ema_* | `201` + row (`id`, `fills`, `pnl_paise`, …) **sync** |
| `get_backtest` | `GET /workbooks/{wid}/backtests/{id}` | same row |
| `start_run` | `POST /workbooks/{wid}/runs/start` | `{router, capital_paise, anchor_date:"YYYY-MM-DD"}` for hist/live; **prefer past day for agent** | `201` + `run_id`, `selected`, `fills`, … |
| `run_events` | `GET /workbooks/{wid}/runs/{rid}/events?include=routing,fill` | event list |

**Time helper (must implement in Python):**

```python
# IST session day → nanos (match AlgoCraft session_calendar: IST = UTC+5:30)
# from_ns = IST midnight start of day as UTC epoch nanos
# to_ns   = IST 23:59 end (or next day 00:00 - 1m) as used by UI
```

Prefer computing from `zoneinfo.ZoneInfo("Asia/Kolkata")`.  
“Last week” → last 5 NSE session days ending at last **closed** session (not today if still open).

**Hist run tip:** send `anchor_date` for a **past** trading day so path is hist replay, not live.

### 6.2 Phase B/C agent tools (implemented in C++)

All under `/agent/strategies/*`, JWT required.

#### `POST /agent/strategies/compile`
```json
{
  "name": "my_mean_revert",
  "class_name": "MyMeanRevert",
  "kind": "strategy",
  "hpp": "#pragma once\n...",
  "cpp": "#include \"algocraft/strategies/my_mean_revert.hpp\"\n..."
}
```
- `name`: `^[a-z][a-z0-9_]{0,63}$`
- Response `200` if ok, `422` if compile failed: `{ok, name, class_name, sandbox_dir, log}`
- Sandbox on disk: `data/agent_sandbox/<name>/` (C++ side). No catalog enable.

#### `POST /agent/strategies/promote`
```json
{ "name": "my_mean_revert" }
```
- Requires prior successful compile artifacts in sandbox.
- Writes `include/algocraft/strategies/<name>.hpp`, `src/strategies/<name>.cpp`
- Patches `CMakeLists.txt` + `strategy_registrations.cpp`
- Upserts `strategy_catalog` with **`enabled=0`**
- `201`: `{ok, id, name, class_name, enabled:false, hpp_path, cpp_path, log, note}`

#### `POST /agent/strategies/activate`
```json
{ "name": "my_mean_revert", "enabled": true }
```
- `enabled: false` deactivates.
- `200`: catalog row + note to rebuild/restart.

#### `GET /agent/strategies/catalog`
- Array of catalog rows (`id`, `kind`, `name`, `class_name`, `enabled`, paths, `compile_ok`, …).

### 6.3 Generated strategy shape (Phase B LLM must follow)

Mirror existing strategies (e.g. `live_run_testing`, `hammer_reversal`):

- Class `final : public Strategy` in namespace `algocraft`
- Methods: `configure`, `on_bar`, `on_fill`, `on_order_update`, `should_exit`, `metadata`
- `metadata().name` == snake `name`
- `TradingMode::Mis`, `BarResolution::OneMin` unless user asks otherwise
- Include `make_intent.hpp`, `session_clock.hpp`, `position_sizer.hpp` as needed
- Header path: `#include "algocraft/strategies/<name>.hpp"`

Do **not** invent new build systems; C++ compile API only syntax-checks with project `-Iinclude`.

---

## 7. Repo layout (create exactly)

```
AlgoCraft-Agent/
  ARCHITECTURE.md          ← copy of this file (Notes/AI_AGENT.md)
  README.md
  pyproject.toml
  .env.example             ← ports, C++ URL, AGENT_SECRETS_FILE path, agent thresholds
  .gitignore
  .cursorignore            ← ignore secrets paths if ever under the tree
  config/
    llm_catalog.yaml       ← COMMITTED allowlist: providers + models (UI source of truth)
  docs/
    cpp/
      INDEX.md             ← always in LLM context (path + one-line about)
      *.md                 ← core contracts; fetch ≤2–3 (see §7.1)
      strategies/          ← one md per registered strategy + INDEX.md
      indicators/          ← library + each indicator + INDEX.md
      routing/             ← interface + each router + INDEX.md
  app/
    __init__.py
    main.py                # FastAPI app + CORS + routers
    config.py              # pydantic-settings from env (+ load AGENT_SECRETS_FILE)
    api/
      __init__.py
      health.py
      llm_catalog.py       # GET /v1/llm/catalog
      sessions.py
      chat.py
      confirm.py
    graph/
      __init__.py
      state.py
      graph.py             # build_graph() → compiled LangGraph
      nodes/
        classify.py
        research.py
        propose.py
        execute.py
        evaluate.py
        respond.py
        design_code.py
        compile_loop.py
        human_gate.py
    tools/
      __init__.py
      algocraft_client.py  # httpx.AsyncClient, Bearer, timeouts
      market.py
      backtest.py
      routing.py
      agent_lifecycle.py   # compile/promote/activate/catalog
      timeutil.py          # IST ↔ nanos
    llm/
      catalog.py           # load + validate llm_catalog.yaml
      factory.py           # get_chat_model(provider, model, temperature) — ONLY switch point
      prompts.py
    store/
      sessions.py          # in-memory SessionStore (holds provider/model)
    models/
      api.py               # request/response schemas
  tests/
    conftest.py
    test_timeutil.py
    test_evaluate.py
    test_llm_catalog.py
    test_client_mock.py
    test_graph_phase_a.py
```

**Secrets file (NOT in this repo):** user keeps e.g. `~/secrets/algocraft-llm.env` (or sibling outside `MAIN_PROJECTS`). Point `AGENT_SECRETS_FILE` at it. Ship only `llm.secrets.env.example` (dummy key names, empty values) for copy-paste — never real keys.

### 7.1 C++ knowledge docs (`docs/cpp/`)

Curated agent-facing slices of the AlgoCraft C++ surface (not a dump of `AlgoCraft/Notes/`).

| Rule | Detail |
|------|--------|
| Index always | Load `docs/cpp/INDEX.md` into relevant nodes (design_code, compile_loop, research). |
| Selective fetch | From the index table, load **at most 2–3** other doc paths per turn. |
| Catalog folders | `strategies/`, `indicators/`, `routing/` each have their own `INDEX.md` (path + one-line); drill into one body file after picking from that folder index. |
| Codegen default | Prefer `codegen_shape.md` + `strategy_interface.md`; add sizing/clock/indicators as needed. |
| Loader | Implement `app/docs_loader.py`: parse index → resolve paths → read files. Optional LLM tool `fetch_doc(path)`. |
| Source of truth | Human architecture stays in AlgoCraft `Notes/`; keep `docs/cpp/` concise and sync when Strategy/API/registry lists change. |

### Package manager

Use **uv** (not pip):

```bash
uv sync --group dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
uv run pytest
```

`uv.lock` and `.python-version` (3.12) are committed.

### `pyproject.toml` deps (minimum)

```toml
[project]
name = "algocraft-agent"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "httpx>=0.27",
  "pydantic>=2.8",
  "pydantic-settings>=2.5",
  "langgraph>=0.2",
  "langchain-core>=0.3",
  "langchain-openai>=0.2",
  "langchain-google-genai>=2.0",
  "pyyaml>=6.0",
  "sse-starlette>=2.1",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "ruff>=0.6"]
```

---

## 8. LLM multi-provider (locked)

### 8.1 Split of concerns

| Artifact | Location | Committed? | Contains |
|----------|----------|------------|----------|
| `config/llm_catalog.yaml` | Inside repo | **Yes** | Providers + allowlisted models. Product policy; **intersected** with live list-models for UI (§8.7). |
| Repo `.env` / `.env.example` | Inside repo | example yes | Ports, C++ URL, `AGENT_SECRETS_FILE`, agent thresholds. **No LLM API keys.** |
| `llm.secrets.env` (user file) | **Outside** repo (path via `AGENT_SECRETS_FILE`) | **No** | `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY` only |
| `llm.secrets.env.example` | Inside repo | Yes (dummy) | Empty key names for the user to copy elsewhere |

Frontend never sees keys. Catalog API never returns keys. Cursor/agents must not read the real secrets file (keep it outside the workspace or list it in `.cursorignore`).

### 8.2 Catalog YAML shape

```yaml
# config/llm_catalog.yaml
default_provider: groq
default_model: openai/gpt-oss-20b
default_temperature: 0.2
temperature_min: 0.0
temperature_max: 2.0

providers:
  deepseek:
    label: DeepSeek
    base_url: https://api.deepseek.com
    env_key: DEEPSEEK_API_KEY
    models:
      - id: deepseek-chat
        label: DeepSeek Chat
      - id: deepseek-reasoner
        label: DeepSeek Reasoner

  gemini:
    label: Google Gemini
    # no base_url — uses Google GenAI SDK
    env_key: GEMINI_API_KEY
    models:
      - id: gemini-3.8-flash
        label: Gemini 3.8 Flash
      - id: gemini-2.5-flash
        label: Gemini 2.5 Flash
      - id: gemini-2.5-pro
        label: Gemini 2.5 Pro

  openrouter:
    label: OpenRouter
    base_url: https://openrouter.ai/api/v1
    env_key: OPENROUTER_API_KEY
    models:
      - id: deepseek/deepseek-chat
        label: DeepSeek Chat (via OR)
      - id: meta-llama/llama-3.3-70b-instruct
        label: Llama 3.3 70B (via OR)
      - id: google/gemini-2.0-flash-001
        label: Gemini Flash (via OR)

  groq:
    label: Groq
    base_url: https://api.groq.com/openai/v1
    env_key: GROQ_API_KEY
    models:
      - id: openai/gpt-oss-20b
        label: GPT-OSS 20B
      - id: openai/gpt-oss-120b
        label: GPT-OSS 120B
      - id: qwen/qwen3.8-27b
        label: Qwen3.8 27B
```

Rules:
- YAML = **product allowlist** (what we are willing to expose). Not every remote model is offered.
- **Live discovery (§8.7):** `GET /v1/llm/catalog` intersects YAML with each provider’s list-models API so dropdowns only show models that exist/are reachable for that key.
- No free-text model strings from the client.
- Keep **native** DeepSeek / Gemini / Groq **and** OpenRouter. Preference for defaults / fallbacks: **groq → gemini → openrouter → deepseek (last)**.

### 8.3 Factory — the only switch point

```text
(provider, model, temperature) from session / chat
    → catalog.resolve() + clamp_temperature()
    → get_chat_model(provider, model, temperature)  # app/llm/factory.py
    → LangGraph configurable["llm"]
    → nodes call llm.ainvoke(...)
    → on 429/quota → structured rate_limit error (§8.8); do NOT auto-switch
```

| Provider | Implementation |
|----------|----------------|
| `deepseek`, `openrouter`, `groq` | `ChatOpenAI` + `base_url` + `api_key` + **`temperature` from UI** |
| `gemini` | `ChatGoogleGenerativeAI` + `google_api_key` + **`temperature` from UI** |

- Graph nodes **must not** `if provider == ...`.
- Cache clients by `(provider, model, temp_rounded_2dp)` (`lru_cache`); do not put secrets in the cache key.
- Temperature: catalog `default_temperature` (0.2), clamp to `[temperature_min, temperature_max]` (default 0–2). Out of range → 422.
- Missing env key → clear error / catalog `available: false` for that provider.

### 8.4 Secrets dummy (`llm.secrets.env.example`)

```bash
# Copy to a path OUTSIDE this repo, fill values, set AGENT_SECRETS_FILE in .env
DEEPSEEK_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
GROQ_API_KEY=
```

Startup: load repo `.env`, then `load_dotenv(AGENT_SECRETS_FILE, override=True)` so keys land in `os.environ` for the factory.

### 8.5 Repo `.env.example` (no API keys)

```bash
AGENT_HOST=127.0.0.1
AGENT_PORT=8100

ALGOCRAFT_API_URL=http://127.0.0.1:8080
ALGOCRAFT_USER=agent_bot
ALGOCRAFT_PASS=changeme

# Absolute path to secrets file outside the repo (user-managed)
AGENT_SECRETS_FILE=/absolute/path/to/llm.secrets.env

# Optional defaults if session omits provider/model (must exist in llm_catalog.yaml)
# Prefer groq/gemini; DeepSeek last.
# AGENT_DEFAULT_LLM_PROVIDER=groq
# AGENT_DEFAULT_LLM_MODEL=openai/gpt-oss-20b

AGENT_MAX_ITERATIONS=3
AGENT_MAX_COMPILE_ATTEMPTS=5
AGENT_MIN_FILLS=2
AGENT_MAX_FILLS=5000
AGENT_SOFT_MIN_PNL_PAISE=1
AGENT_HTTP_TIMEOUT_SEC=120
AGENT_HTTP_LONG_TIMEOUT_SEC=600
AGENT_COMPILE_TIMEOUT_SEC=180
```

### 8.6 Catalog API response (for dropdowns)

```json
{
  "default_provider": "groq",
  "default_model": "openai/gpt-oss-20b",
  "default_temperature": 0.2,
  "temperature_min": 0.0,
  "temperature_max": 2.0,
  "providers": [
    {
      "id": "groq",
      "label": "Groq",
      "available": true,
      "status": "ok",
      "models": [
        {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B", "reachable": true}
      ]
    }
  ]
}
```

Fields:
- `available` — key present in env  
- `status` — `ok` | `no_key` | `unreachable` | `rate_limited` (best-effort)  
- `default_temperature` / `temperature_min` / `temperature_max` — drive the UI temp control  
- `models[]` — YAML allowlist **∩** live list-models (§8.7); `reachable: false` if listed in YAML but missing from provider API  

UI: grey out `available=false` / `status!=ok` providers; model dropdown only shows `reachable=true` (or show unreachable greyed with tooltip); temperature slider uses min/max/default.

### 8.7 Live model discovery (locked)

User does not hardcode “what exists today.” On `GET /v1/llm/catalog` (and optionally a short TTL cache, e.g. 5–15 min):

1. Load YAML allowlist.  
2. For each provider with a key set, call that provider’s **list models** endpoint (OpenAI-compat `GET {base_url}/models`; Gemini via Google list-models).  
3. **Intersect:** dropdown models = YAML models whose `id` appears in the live list (normalize ids per provider).  
4. If list-models fails (network / 401 / 429): keep YAML models but set `status=unreachable` or `rate_limited`; do not invent ids.  
5. Never expose raw provider payloads or keys to the UI.

Implement in `app/llm/discover.py`; catalog API uses it. Chat still validates against YAML allowlist (defense in depth).

### 8.8 Rate limits / quota exhausted (locked)

Free tiers hit RPM/RPD/TPM caps. **Do not auto-switch providers.**

When an LLM call returns **429**, quota, or clear “rate limit / resource exhausted” body:

1. Stop the graph turn cleanly (no silent retry storm; at most **one** short retry if `Retry-After` is tiny and we choose to support it later — v1: **no auto-retry**).  
2. Surface a structured error to the UI:

**SSE:** `event: error` with payload like:
```json
{
  "code": "llm_rate_limited",
  "provider": "groq",
  "model": "openai/gpt-oss-20b",
  "message": "This provider hit its rate/quota limit. Switch provider or model in the dropdowns and try again."
}
```

**Sync chat JSON:** same `code` / `message` in the error body.

3. UI copy (required): tell the user the **limit was reached**, show which provider/model, and **prompt them to switch provider or model** (existing dropdowns) — then resend.  
4. Optional: set that provider’s catalog `status=rate_limited` for the TTL window so the dropdown can warn before the next call.

### 8.9 Quota-safe building / agent usage (locked)

Keys are on **free plans**. While implementing this repo:

| Rule | Detail |
|------|--------|
| Unit/graph tests | **Mock** LLM + C++ client — zero real LLM HTTP |
| Cursor/agent while coding | Do **not** burn chat completions to “try the model”; use mocks unless the user explicitly asks for a live LLM smoke |
| Live smoke (when asked) | Prefer **groq** or **gemini**; **openrouter** next; **deepseek last / only when necessary** |
| Catalog discovery | List-models is cheap vs chat; still cache TTL; don’t poll every keystroke |
| Default YAML defaults | Prefer groq small/fast model, not DeepSeek |

---

## 9. `AlgocraftClient` requirements

```python
class AlgocraftClient:
    def __init__(self, base_url: str, jwt: str | None = None, ...): ...
    def with_jwt(self, jwt: str) -> Self: ...

    async def login(self, user: str, password: str) -> str: ...
    async def list_strategies(self) -> list[str]: ...
    async def list_routers(self) -> list[str]: ...
    async def search_instruments(self, q: str, limit: int = 20) -> list[dict]: ...
    async def ensure_market_data(self, body: dict) -> dict: ...
    async def create_workbook(self, name: str, capital_paise: int) -> int: ...
    async def start_backtest(self, wid: int, *, ticker, strategy, from_ns, to_ns, capital_paise, **kw) -> dict: ...
    async def start_run(self, wid: int, *, router, capital_paise, anchor_date: str, **kw) -> dict: ...
    async def run_events(self, wid: int, rid: int, include: str = "routing,fill") -> list: ...

    async def agent_compile(self, name: str, hpp: str, cpp: str, class_name: str = "") -> dict: ...
    async def agent_promote(self, name: str) -> dict: ...
    async def agent_activate(self, name: str, enabled: bool = True) -> dict: ...
    async def agent_catalog(self) -> list[dict]: ...
```

Raise `AlgocraftApiError(status, body)` on non-2xx. Never log JWT.

---

## 10. Security checklist

1. Allow-listed tools only — no arbitrary URL/path from LLM  
2. Strategy `name` validated client-side same regex as C++  
3. Human confirm before promote/activate  
4. Rate-limit chat (e.g. 20 req/min/session)  
5. Secrets in external `AGENT_SECRETS_FILE` / env only — never in YAML, logs, API responses, or `AgentState`  
6. LLM `(provider, model)` allowlisted via `config/llm_catalog.yaml` — reject anything else  
7. Phase A must not call promote/activate  
8. Do not pass client-supplied `base_url` or raw API keys into the factory  

---

## 11. Acceptance tests

### Unit
- `timeutil`: known IST day → nanos round-trip sanity  
- `evaluate`: fills/pnl → pass/weak/fail  
- `llm/catalog`: resolve known pair OK; unknown provider/model raises  
- `llm/factory`: (mocked env) OpenAI-compat vs gemini path selected correctly  
- Graph with **mocked** client: backtest intent ends in `respond` with metrics  

### Integration (optional, needs serve)
1. Login / forward JWT  
2. `GET /v1/llm/catalog` returns providers; no key fields in JSON  
3. `list_strategies` non-empty  
4. Backtest `hammer_reversal` on one ticker short window  
5. Hist `runs/start` with `live_run_testing_router` or `top15_week_router` + past `anchor_date`  
6. Compile a tiny valid strategy (can copy stripped `live_run_testing` renamed) → `ok=true`  
7. Promote → catalog `enabled=false` → activate → `enabled=true`  

### Manual UX
```
User: Backtest hammer_reversal on ONGC for last 5 sessions with 1L
→ card with fills, pnl_paise, verdict
(UI: provider dropdown → model dropdown → chat uses that pair)
```

---

## 12. Implementation order (checklist)

- [x] 1. Repo + `pyproject.toml` + `.env.example` + `llm.secrets.env.example` + `.gitignore` / `.cursorignore` + README + copy this → `ARCHITECTURE.md`  
- [x] 2. `config/llm_catalog.yaml` + `app/llm/catalog.py` + `factory.py` + `GET /v1/llm/catalog`  
- [x] 3. `config.py` (load secrets file) + `/healthz` (ping C++ `/strategies` or `/auth/me`)  
- [x] 4. `AlgocraftClient` + `timeutil` + unit tests  
- [x] 5. `SessionStore` + `POST /v1/sessions` (+ provider/model) + `PATCH .../llm`  
- [x] 5b. `app/llm/discover.py` (list-models ∩ YAML) + rate-limit error mapping (§8.7–8.8)  
- [x] 6. LangGraph Phase A nodes + mock tests (inject `configurable["llm"]`) — **no live LLM in CI**  
- [x] 7. Wire real backtest + evaluate  
- [x] 8. Wire hist `start_run` + events — client + graph `route`→`start_run`→`run_events` + live smoke  
- [x] 9. `POST /v1/chat` + SSE stream  
- [x] 10. Phase B `design_code` + `compile_loop` — graph branch `codegen_strategy`→design→compile≤5; template fallback when `llm=None`; `pending_human=promote` on ok (no promote)  
- [x] 11. Phase C confirm + promote + activate — `POST .../confirm`, `APPROVE_*` chat, human_gate + promote/activate nodes; no auto-promote  
- [ ] 12. (Separate) AlgoCraft-UI: provider/model dropdowns + chat panel  

---

## 13. Decision summary (locked)

| Topic | Decision |
|-------|----------|
| Framework | FastAPI + LangGraph StateGraph |
| Agent port | **8100** |
| C++ port | **8080** |
| Auth | Forward user JWT to C++ |
| LLM UX | UI: **provider → model** dropdowns + **temperature** control; on rate/quota limit → tell user to **switch** (no auto-switch) |
| LLM catalog | YAML allowlist **∩** live list-models (`discover.py`); short TTL cache |
| LLM secrets | External file via `AGENT_SECRETS_FILE`; dummy example in repo only |
| LLM switch | Single factory `get_chat_model(provider, model, temperature)`; OpenAI-compat for deepseek/openrouter/groq; GenAI SDK for gemini |
| LLM injection | LangGraph `configurable["llm"]`; never store API keys in state |
| LLM defaults / preference | **groq → gemini → openrouter → deepseek (last)** |
| LLM while coding | Mock in tests; no chat-completion burn; live smoke only when user asks |
| Providers (v1) | `deepseek`, `gemini`, `openrouter`, `groq` |
| Phase A | Existing strategies/routers only |
| Phase B/C C++ | `/agent/strategies/compile\|promote\|activate` + `GET .../catalog` (**done in AlgoCraft**) |
| Promote | Catalog `enabled=0` |
| Activate | Catalog `enabled=1`; rebuild+restart to load code |
| Eval | Soft pass/weak/fail |
| Hist default | Past `anchor_date` |
| Long timeout | 600s runs/backtests |
| UI chat panel | Later (dropdowns + chat) |

---

## 14. Sibling references

| Path | Why |
|------|-----|
| `AlgoCraft/src/api/agent_routes.cpp` | Exact agent HTTP handlers |
| `AlgoCraft/src/strategies/strategy_compiler.cpp` | Sandbox + promote file rules |
| `AlgoCraft/migrations/schema_009.sql` | `strategy_catalog` |
| `AlgoCraft/src/strategies/live_run_testing.*` | Minimal strategy template |
| `AlgoCraft/src/api/workbook_routes.cpp` | backtest/run body fields |

---

*When starting: keep `Notes/AI_AGENT.md` and root `ARCHITECTURE.md` in sync; implement checklist §12 in order. Part 1 = checklist items 1–3 (skeleton, LLM catalog/factory, config + healthz).*
