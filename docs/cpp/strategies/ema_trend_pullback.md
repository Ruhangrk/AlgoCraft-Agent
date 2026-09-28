# `ema_trend_pullback`

| | |
|--|--|
| Class | `EmaTrendPullback` |
| Registry name | `ema_trend_pullback` |
| Typical StrategyId const | `12` (local; router may reassign) |
| Indicators | EMA 9/21 |
| Resolution / mode | OneMin / MIS |

## Idea
Uptrend (EMA9 > EMA21) buy pullback when close is within ~8 bps above EMA9.

## Exit
EMA9 < EMA21 or −35 bps stop.

## Sizing / session
45% cash, leverage 1. No entries ≥ **14:30**. Periods hardcoded 9/21 in strategy.

## When to fetch
Trend pullback to fast EMA.

