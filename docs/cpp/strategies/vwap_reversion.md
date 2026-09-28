# `vwap_reversion`

| | |
|--|--|
| Class | `VwapReversion` |
| Registry name | `vwap_reversion` |
| Typical StrategyId const | `2` (local; router may reassign) |
| Indicators | VWAP |
| Resolution / mode | OneMin / MIS |

## Idea
Mean-revert to session VWAP when price is stretched below/above by `vwap_dev_paise`.

## Indicators
`lib.get<Vwap>(symbol, OneMin)`.

## Entry
Flat and close ≤ VWAP − `vwap_dev_paise` (default 50 paise).

## Exit
Long and close ≥ VWAP + `vwap_dev_paise`.

## Sizing / session
`order_qty`. No hardcoded last-entry cutoff.

## When to fetch
VWAP reversion / deviation patterns.

