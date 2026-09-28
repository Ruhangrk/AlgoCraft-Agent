# `dip5_mean_revert`

| | |
|--|--|
| Class | `Dip5MeanRevert` |
| Registry name | `dip5_mean_revert` |
| Typical StrategyId const | `8` (local; router may reassign) |
| Indicators | LaggedSma(5) |
| Resolution / mode | OneMin / MIS |

## Idea
Buy dips ≤ prior-5 avg − 25 bps; exit when back to avg or hard stop.

## Exit
Close ≥ avg (flatten) or −50 bps stop.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
Short-horizon mean reversion to lagged SMA.

