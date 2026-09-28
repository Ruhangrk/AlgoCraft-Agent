# `compression_break`

| | |
|--|--|
| Class | `CompressionBreak` |
| Registry name | `compression_break` |
| Typical StrategyId const | `16` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
4 tiny-range bars then close ≥ compression high + 20 bps.

## Exit
+40 bps TP or −30 bps SL.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
Volatility compression → expansion.

