# `bull_harami_break`

| | |
|--|--|
| Class | `BullHaramiBreak` |
| Registry name | `bull_harami_break` |
| Typical StrategyId const | `22` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
Bull harami arms; buy on break above mother candle high.

## Exit
TP/SL or close < mother low.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
Harami + breakout confirmation.

