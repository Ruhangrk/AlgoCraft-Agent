# Vwap

| | |
|--|--|
| Class | `Vwap` |
| `kTypeName` | `"VWAP"` |
| Header | `algocraft/indicators/vwap.hpp` |

## get args
`(SymbolId, BarResolution::OneMin)` — no period arg.

## ready / value
- `ready`: volume_sum > 0
- `value`: session VWAP (typical price × vol / vol); resets each calendar day

## Typical use
`vwap_reversion`, `vwap_reclaim_long`, `bajaj_custom_strategy`.
