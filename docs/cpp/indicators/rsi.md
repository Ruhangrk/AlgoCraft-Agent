# Rsi

| | |
|--|--|
| Class | `Rsi` |
| `kTypeName` | `"RSI"` |
| Header | `algocraft/indicators/rsi.hpp` |

## get args
`(SymbolId, BarResolution::OneMin, int period)` — often `config.rsi_period` (14).

## ready / value
- `ready` after Wilder warm-up
- `value`: RSI 0–100

## Typical use
Oversold entries / overbought exits (`bajaj_custom_strategy`).
