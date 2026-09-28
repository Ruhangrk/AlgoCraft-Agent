# Sma (daily)

| | |
|--|--|
| Class | `Sma` |
| `kTypeName` | `"SMA"` |
| Header | `algocraft/indicators/sma.hpp` |

## get args
`(SymbolId, BarResolution::OneDay, int period)` — typically `config.sma_period` (200).

## Behavior
Only consumes **OneDay** bars (1m tape ignored). Seed via daily warmup bars from router/container.

## ready / value
- `ready`: window size ≥ period
- `value`: SMA of daily closes

## Metadata
Strategies needing warmup should list `"SMA"` in `required_indicators` so routers call `load_daily_sma_warmup`.
