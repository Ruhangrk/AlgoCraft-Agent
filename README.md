# AlgoCraft-Agent

Python FastAPI + LangGraph agent for AlgoCraft (research, backtest/hist runs, strategy codegen).

## Quick start (Part 1)

```bash
cd AlgoCraft-Agent
uv sync --group dev

# Copy secrets outside the repo, fill keys, then:
cp .env.example .env
# edit AGENT_SECRETS_FILE=/absolute/path/to/your/llm.secrets.env

uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

- `GET /healthz` — agent up + C++ reachability  
- `GET /v1/llm/catalog` — provider/model dropdowns (no API keys)

Tests: `uv run pytest`

## Secrets

1. `cp llm.secrets.env.example ~/secrets/algocraft-llm.env` (path of your choice, **outside** this repo)  
2. Fill `DEEPSEEK_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` / `GROQ_API_KEY`  
3. Set `AGENT_SECRETS_FILE` in `.env` to that absolute path  

Allowlisted models: [`config/llm_catalog.yaml`](config/llm_catalog.yaml).

## C++ knowledge docs

Agent-facing curated docs live under [`docs/cpp/`](docs/cpp/):

- Always share [`docs/cpp/INDEX.md`](docs/cpp/INDEX.md) with the LLM.
- Fetch at most 2–3 other files from that index per turn.

Full build architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md) (synced from [`Notes/AI_AGENT.md`](Notes/AI_AGENT.md)).
