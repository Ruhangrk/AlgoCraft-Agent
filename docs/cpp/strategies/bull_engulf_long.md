# `bull_engulf_long`

| | |
|--|--|
| Class | `BullEngulfLong` |
| Registry name | `bull_engulf_long` |
| Typical StrategyId const | `11` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
Bullish engulfing after a red prior bar.

## Exit
+45 bps TP or −30 bps SL.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
Classic candlestick engulfing longs.

