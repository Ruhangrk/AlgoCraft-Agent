# Ema

| | |
|--|--|
| Class | `Ema` |
| `kTypeName` | `"EMA"` |
| Header | `algocraft/indicators/ema.hpp` |

## get args
`(SymbolId, BarResolution::OneMin, int period)`

## ready / value
- `ready`: `count >= period`
- `value`: EMA of close (close fed as paise `double`)

## Typical use
Crossovers (`ema_crossover`), trend filter / pullback (`ema_trend_pullback`). Prefer `config.ema_fast` / `ema_slow` when available.
