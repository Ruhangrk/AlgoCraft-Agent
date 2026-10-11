# AlgoCraft-Agent

FastAPI + LangGraph service that turns natural-language strategy requests into AlgoCraft C++ strategies: design, compile, iterate on errors, and run backtests against the C++ engine.

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

## Setup

```bash
cd AlgoCraft-Agent
uv sync --group dev

cp .env.example .env
# edit AGENT_SECRETS_FILE and ALGOCRAFT_* as needed
```

LLM keys stay outside the repo:

1. Copy `llm.secrets.env.example` somewhere outside this tree (for example `~/.config/AlgoCraft_Agent/llm.secrets.env`).
2. Fill in the provider keys you use (`GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`).
3. Point `AGENT_SECRETS_FILE` in `.env` at that absolute path.

Allowlisted models live in [`config/llm_catalog.yaml`](config/llm_catalog.yaml).

The C++ engine should be reachable at the URL in `ALGOCRAFT_API_URL` (default `http://127.0.0.1:8080`) with credentials matching `ALGOCRAFT_USER` / `ALGOCRAFT_PASS`. Chat and docs Q&A can run without a live engine; compile/backtest need it.

## Run

```bash
uv run python -m app --log-level info
```

| Flag | Values | Default |
|------|--------|---------|
| `--log-level` / `-l` | `info`, `debug`, `trace` | `info` |
| `--host` | bind address | `127.0.0.1` (or `AGENT_HOST`) |
| `--port` | bind port | `8100` (or `AGENT_PORT`) |

Examples:

```bash
uv run python -m app --log-level debug
uv run python -m app -l trace --port 8100
```

| Level | Includes |
|-------|----------|
| `info` | Operational logs (chat turns, graph start/end, errors) |
| `debug` | Everything in `info`, plus graph node enter/exit (flow) |
| `trace` | Everything in `debug`, plus full LLM prompts/responses and C++ HTTP bodies |

JWT / `Authorization` headers are never logged.

Smoke check:

```bash
curl -s http://127.0.0.1:8100/healthz
```

Plain uvicorn also works (`uv run uvicorn app.main:app --host 127.0.0.1 --port 8100`) but has no `--log-level` for app logs; use `python -m app` for that.

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/healthz` | Agent up; C++ reachability |
| `GET` | `/v1/llm/catalog` | Provider/model list (no keys) |
| `POST` | `/v1/sessions` | Create session (Bearer JWT from C++ login) |
| `POST` | `/v1/chat` | Chat / strategy turn |
| `GET` | `/v1/chat/{session_id}/stream` | SSE for the last chat turn |
| `POST` | `/v1/sessions/{session_id}/confirm` | Confirm pending actions |

Postman collection and local environment: [`postman/`](postman/).

## Tests

```bash
uv run pytest
```

## Docs

| Doc | Contents |
|-----|----------|
| [`Notes/ARCHITECTURE.md`](Notes/ARCHITECTURE.md) | System design |
| [`Notes/CODE_FLOW.md`](Notes/CODE_FLOW.md) | LangGraph / request flow |
| [`Notes/AI_AGENT.md`](Notes/AI_AGENT.md) | Contracts and build checklist |
| [`docs/cpp/`](docs/cpp/) | Curated C++ knowledge fed to the LLM |
