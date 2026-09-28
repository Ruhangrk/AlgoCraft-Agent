# `reliance_prev5_avg_break`

| | |
|--|--|
| Class | `ReliancePrev5AvgBreak` |
| Registry name | `reliance_prev5_avg_break` |
| Typical StrategyId const | `7` (local; router may reassign) |
| Indicators | LaggedSma(5) |
| Resolution / mode | OneMin / MIS |

## Idea
Breakout above prior-5 average + 30 bps.

## Indicators
`LaggedSma(5)` on OneMin (mean of prior 5 closes excluding current).

## Exit
Vs avg: −45 bps stop or +55 bps TP.

## Sizing / session
50% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
Lagged average breakouts.

