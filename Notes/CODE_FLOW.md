# AlgoCraft-Agent — Code flow (how a message runs)

**Companion to:** [`ARCHITECTURE.md`](ARCHITECTURE.md) (what exists)  
**Build / contracts:** [`AI_AGENT.md`](AI_AGENT.md)

This file walks through **code**, especially LangGraph: what each library piece does, and what happens for one user message from HTTP to reply.

---

## 0. Libraries in one paragraph

| Library | Role here |
|---------|-----------|
| **FastAPI** | HTTP: sessions, chat, confirm, health, LLM catalog |
| **LangGraph** | State machine: nodes + edges; runs until `END` |
| **LangChain** | Message types (`HumanMessage`…), chat models (`ChatOpenAI` / Gemini), `RunnableConfig` |
| **httpx** | Async HTTP to AlgoCraft C++ (`AlgocraftClient`) |
| **sse-starlette** | Replay thinking/card/done as Server-Sent Events |

LangGraph is **not** “chat with memory magic.” It is: start with a **state dict**, call **node functions** that return **partial updates**, merge them into state, follow **edges** to the next node.

---

## 1. LangGraph mental model (this repo)

### State

Defined in `app/graph/state.py` as a `TypedDict`. Important fields:

- `messages` — chat turns; reducer `add_messages` **appends** instead of overwrite  
- `thinking` — list of crumbs; reducer `operator.add` **concatenates**  
- Everything else (`intent`, `chosen`, `create_draft`, …) — last write wins  

### Node

A Python async (or sync) function:

```text
async def some_node(state: AgentState, config: RunnableConfig) -> dict:
    # read state…
    return {"intent": "backtest", "thinking": [...]}  # patch only what changed
```

`config["configurable"]` holds **injected deps** (not in state):

- `algocraft` → `AlgocraftClient` (JWT already set)  
- `llm` → LangChain chat model or `None`  

Helpers: `app/graph/nodes/_common.py` (`last_user_text`, `get_client`, `get_llm`).

### Graph

Built once in `app/graph/graph.py`:

1. `StateGraph(AgentState)`  
2. `add_node("name", fn)`  
3. `add_edge` / `add_conditional_edges` (router function looks at state → next node name)  
4. `compile()` → runnable  

Invoke:

```python
result = await graph.ainvoke(initial_state, config={"configurable": {...}})
```

`result` is the **final merged state**.

### Thinking crumbs

`app/graph/thinking.py` → `thought("route", "…")` returns `{"thinking": [{agent, phase, thought, data?}]}`. Nodes spread that into their return so the UI can show a trail.

---

## 2. End-to-end: `POST /v1/chat`

```text
UI / curl
  → app/api/chat.py::post_chat
      → load Session (JWT, provider/model, create_draft, pending_human)
      → if message is APPROVE_PROMOTE / APPROVE_ACTIVATE:
            app/graph/lifecycle.py::run_confirm   ← NOT the main graph
        else:
            app/graph/runner.py::run_phase_a
                → optionally app/llm/factory.py::get_chat_model
                → graph.ainvoke(...)
      → _apply_result_to_session (messages, card, thinking, draft, SSE buffer)
      → ChatResponse JSON
  → optional GET /v1/chat/{id}/stream  (replay SSE events)
```

### Runner (`app/graph/runner.py`)

Builds initial state:

- `messages=[HumanMessage(content=user text)]`  
- `user_jwt`, `workbook_id`, `session_id`  
- `create_draft` copied from session (so create interview continues)  
- `iteration` / `max_iterations`  

Builds LLM if `provider`+`model` set and secrets exist; on failure keeps `llm=None` (rules-only path).

Passes:

```python
config={"configurable": {"algocraft": client, "llm": llm}}
```

---

## 3. Graph walk (every normal turn starts at `route`)

```text
START
  └─ route          always
       ├─ chat | clarify ──────────────────────────────► respond ► END
       ├─ discuss ──► discuss ─────────────────────────► respond ► END
       ├─ backtest | route(hist)
       │     └─ research ► propose ► execute ► evaluate
       │                         ▲               │
       │                         └── _retry ─────┘
       │                                         └─► respond ► END
       └─ create
             └─ create_interview
                   ├─ not ready ───────────────────────► respond ► END
                   └─ ready ► design_code ► compile_loop ► respond ► END
```

Conditional routers live next to the graph in `graph.py`:

- `_route_after_router` — reads `intent`  
- `_route_after_create` — reads `create_ready`  
- `_route_after_evaluate` — reads `_retry`  

---

## 4. Lane-by-lane (what code does)

### A. Chat / clarify

1. **`route`** (`nodes/route.py`)  
   - Rules: greeting → `chat`; garbage → `clarify`; optional LLM JSON if still unclear.  
   - Sets `intent`; may clear `create_draft` on cancel.  
2. **`respond`** (`nodes/respond.py`)  
   - Fixed help / clarify copy; builds `card` + `response_text` + `AIMessage`.

No C++ calls.

### B. Discuss

1. **`route`** — discuss cues or bare strategy name → `intent=discuss`, `topic_strategy`.  
2. **`discuss`** (`nodes/discuss.py`)  
   - Lists strategies from C++ (or fails soft).  
   - `resolve_strategy_mention` (`entities.py`) against catalog + `docs/cpp/strategies/*.md`.  
   - Named hit → load doc, optional LLM summary; else catalog list + ask which name.  
3. **`respond`** — surfaces `discuss_summary`.

### C. Backtest / hist (`intent` = `backtest` or `route`)

1. **`route`** — backtest cues / typos / “with strategy …” + ticker (`entities.looks_like_backtest`).  
2. **`research`** — `list_strategies`, `list_routers`, notes into state.  
3. **`propose`** — match strategy/router name; parse date or last N sessions (`timeutil`); fill `chosen` (`strategy`+`ticker`+`from_ns`/`to_ns` or `router`+`anchor_date`).  
4. **`execute`** — create workbook if needed; `ensure_market_data`; then `start_backtest` **or** `start_run` + `run_events`; store `cpp_results` / `workbook_id`.  
5. **`evaluate`** — fills/pnl thresholds → `pass` / `weak` / `fail`; may `_retry` → propose again (capped by `max_iterations`).  
6. **`respond`** — human summary of metrics + card.

### D. Create (new strategy)

1. **`route`** — create verbs → `intent=create`, open `create_draft` (`status=interviewing`).  
2. **`create_interview`** — merge ticker + idea (+ optional name) into draft.  
   - Missing → `create_ready=False`, `interview_prompt` → respond asks questions.  
   - Complete → `create_ready=True`, `chosen={name, class_name, idea, ticker}` → design.  
3. **`design_code`** — LLM or template → `hpp`/`cpp` in `chosen`.  
4. **`compile_loop`** — `agent_compile` up to 5; on success `pending_human=promote` (does **not** promote).  
5. **`respond`** — “confirm promote” style message.  

Session keeps `create_draft` / `pending_human` / `pending_strategy_name` for the next turn.

### E. Phase C (outside the main graph)

`APPROVE_PROMOTE` / `APPROVE_ACTIVATE` or `POST .../confirm`:

```text
lifecycle.run_confirm
  → human_gate  (pending_human must match)
  → promote | activate  (C++ agent APIs)
  → respond
```

Manual merge of thinking (no LangGraph reducer) inside `lifecycle.py`.

---

## 5. Natural language (`entities.py`)

Not a graph node — shared helpers used by `route`, `propose`, `discuss`, `create_interview`:

| Helper | Purpose |
|--------|---------|
| `extract_tickers` | `RELIANCE`, `M&M`, … |
| `extract_strategy_likes` | `snake_case` tokens |
| `parse_user_date` | `28th sept 26` → `2026-09-28` |
| `looks_like_backtest` / `looks_like_discuss` | Intent cues + typo fuzzy match |
| `match_catalog_name` / `resolve_strategy_mention` | Bind text → real strategy id (+ local docs) |

Rules first; LLM only when wired and still ambiguous (or for prose in discuss/codegen).

---

## 6. LLM path

```text
Session / chat body: provider + model + temperature
  → catalog allowlist (config/llm_catalog.yaml)
  → factory.get_chat_model → ChatOpenAI (groq/deepseek/openrouter) or Gemini
  → configurable["llm"]
  → nodes call await llm.ainvoke([SystemMessage, HumanMessage])
```

If no key / factory fails → `llm=None` → rules + templates still work for chat/backtest/discuss-from-docs.

Rate limits: `app/llm/errors.py` → chat returns structured `llm_rate_limited` (no auto provider switch).

---

## 7. C++ client path

`app/tools/algocraft_client.py` — one place for HTTP. Nodes never invent URLs.

Typical backtest chain inside `execute`:

```text
create_workbook (if needed)
  → ensure_market_data
  → start_backtest(ticker, strategy, from_ns, to_ns, capital_paise)
```

Hist:

```text
start_run(router, anchor_date, capital_paise)
  → run_events(...)
```

Time: `app/tools/timeutil.py` (IST session days ↔ epoch nanos).

---

## 8. Session + SSE

`app/store/sessions.py` — in-memory `Session`:

- Auth + LLM selection  
- `messages`, `last_card`, `last_thinking`  
- `create_draft`, `pending_human`, `pending_strategy_name`  
- `stream_events` — built after each chat turn  

SSE (`GET .../stream`) **replays** those events (`thinking`, `tool`, `token`, `card`, `error`, `done`). It is not a live token stream of the LLM mid-node (v1 = post-turn replay).

---

## 9. Worked examples (follow in a debugger)

### Example 1 — `"hi"`

```text
route → intent=chat → respond → END
thinking: route, respond
C++: none
```

### Example 2 — `"two_consecutive_bars lets discuss this"`

```text
route → discuss → discuss node (load docs/cpp/strategies/two_consecutive_bars.md)
     → respond → END
```

### Example 3 — `"backest M&M for 28th sept 26, with strategy hammer_reversal"`

```text
route → backtest
research → candidates
propose → chosen={strategy:hammer_reversal, ticker:M&M, session_from:2026-09-28, …}
execute → C++ backtest
evaluate → pass/weak/fail
respond → "Backtest `hammer_reversal` on `M&M` …"
```

### Example 4 — `"create a strategy that buys after two red bars"`

```text
route → create (draft active)
create_interview → missing ticker → respond asks for ticker
(next turn) user: "RELIANCE"
  → create_interview → ready → design_code → compile_loop → respond (pending promote)
```

---

## 10. Where to open files (reading order)

| Order | File | Why |
|------:|------|-----|
| 1 | `app/api/chat.py` | HTTP entry + approve vs graph |
| 2 | `app/graph/runner.py` | Initial state + configurable |
| 3 | `app/graph/graph.py` | Edges / lanes |
| 4 | `app/graph/nodes/route.py` | First decision |
| 5 | `app/graph/nodes/entities.py` | How text is understood |
| 6 | Lane file (`discuss` / `propose`+`execute` / `create_interview`+…) | Body of that path |
| 7 | `app/graph/nodes/respond.py` | What the user sees |
| 8 | `app/graph/lifecycle.py` | Phase C after compile |

Product map without this depth: [`ARCHITECTURE.md`](ARCHITECTURE.md).
