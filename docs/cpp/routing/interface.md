# RoutingAlgo interface

Header: `algocraft/routing/routing_algo.hpp`.

## Types
- `RoutingConfig` — workbook, stocks, strategies, from/to, `eval_capital` (default ₹10L paise)
- `RouterDefaults` — `tickers`, `strategies`, `eval_sessions` (HTTP does not pass universe)
- `StrategyEvalResult` — symbol, ticker, strategy_name, pnl_paise, fills, bars, selected, …

## Virtual API
`defaults`, `configure`, `start(data, strategies, containers)`, `on_bar`, session hooks, `stop`, `evaluations`, `name`.

## Typical start flow
1. Evaluate every (symbol × strategy) via `BacktestRunner` on eval window
2. Mark `selected` winners (all profitable, or top-N)
3. Equal-split `containers.available_capital()` across winners
4. `containers.create(...)`; optionally attach daily SMA warmup bars

## Agent note
v1 codegen is **strategies only**. Pick an existing router by name for `runs/start`.
