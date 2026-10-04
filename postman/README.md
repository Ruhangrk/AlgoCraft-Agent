# Postman — AlgoCraft-Agent

Import both files into Postman (or Insomnia / Bruno with Postman import):

1. [`AlgoCraft-Agent.postman_collection.json`](AlgoCraft-Agent.postman_collection.json)
2. [`AlgoCraft-Agent.postman_environment.json`](AlgoCraft-Agent.postman_environment.json)

Select environment **AlgoCraft-Agent Local**.

## Prerequisites

```bash
# C++ :8080
# Agent :
cd AlgoCraft-Agent
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Set `cpp_username` / `cpp_password` in the environment to a real AlgoCraft user (defaults match `.env.example`: `agent_bot` / `changeme`).

## Suggested order

| # | Request | Saves |
|---|---------|--------|
| 1 | **0. Setup → C++ Login** | `jwt` |
| 2 | **1. Health & Catalog → GET healthz** | — |
| 3 | **2. Sessions → Create session (defaults only)** | `session_id` |
| 4 | **3. Chat → Chat — hi** | — |
| 5 | discuss / backtest / create as needed | — |
| 6 | **4. Stream** after any chat | — |

Backtest/create need a live C++ engine and (for backtests) market data. Chat/clarify/discuss (docs) work with less.

## Auth reminder

JWT comes from **C++** `/auth/login`. Agent only needs Bearer on **Create session**; later chat uses `session_id` and the stored JWT when calling C++.
