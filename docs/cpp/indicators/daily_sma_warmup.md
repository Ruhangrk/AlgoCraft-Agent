# Daily SMA warmup helpers

Header: `algocraft/indicators/daily_sma_warmup.hpp` (not an `Indicator` subclass).

## Purpose
Load ~320 calendar days of **OneDay** bars so `Sma` can warm before 1m trading.

## Key APIs
- `strategy_needs_daily_sma(metadata)` — true if `"SMA"` in `required_indicators`
- `load_daily_sma_warmup(loader, symbol_id, as_of)` → `vector<BarEvent>`
- Constants: `kDefaultSmaPeriod=200`, `kSmaCalendarLookbackDays=320`

## Who calls it
Routers (`default_router`, `top15_week_router`) when creating containers for SMA strategies. Agent-authored strategies that need 200DMA must declare `"SMA"` in metadata.
