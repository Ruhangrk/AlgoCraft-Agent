# AlgoCraft C++ docs index

Always load this file. Then fetch **at most 2–3** other paths that match the user task (a folder INDEX counts as one if you only need the catalog).

## Core (contracts / codegen)

| path | about |
|------|--------|
| docs/cpp/units_and_types.md | Money/time units; Price Quantity Capital Timestamp Side |
| docs/cpp/strategy_interface.md | Strategy base API, config, metadata, lifecycle |
| docs/cpp/make_intent_and_sizing.md | make_intent, OrderIntent, position_for_capital |
| docs/cpp/session_clock.md | IST minutes, NSE hours, last-entry cutoffs |
| docs/cpp/indicators.md | Quick indicator overview (see also indicators/) |
| docs/cpp/portfolio_and_fills.md | PortfolioView, on_fill, TP/SL in bps |
| docs/cpp/codegen_shape.md | Exact hpp/cpp shape agent must emit |
| docs/cpp/agent_apis.md | compile promote activate catalog HTTP |
| docs/cpp/engine_http_apis.md | Workbook backtest run market JWT tools |
| docs/cpp/routers.md | Quick router overview (see also routing/) |
| docs/cpp/examples.md | Patterns from hammer ema live_run_testing |
| docs/cpp/pitfalls.md | Common codegen mistakes to avoid |

## Catalog folders (pick then drill)

| path | about |
|------|--------|
| docs/cpp/strategies/INDEX.md | All registered strategies — path + one-line |
| docs/cpp/indicators/INDEX.md | All indicators + library — path + one-line |
| docs/cpp/routing/INDEX.md | All routing algos — path + one-line |

## Fetch rules
1. Codegen / fix compile → `codegen_shape.md` + `strategy_interface.md`; add others as needed.
2. Mimic an existing strategy → `strategies/INDEX.md` then **one** `strategies/<name>.md`.
3. Bind indicators → `indicators/INDEX.md` then `library.md` + concrete indicator.
4. Choose hist/live router → `routing/INDEX.md` then one router file.
5. Calling C++ from Python → `agent_apis.md` and/or `engine_http_apis.md`.
6. Max **2–3** body docs per turn after this index (folder INDEX optional extra).
