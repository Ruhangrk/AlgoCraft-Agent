# `five_bar_high_break`

| | |
|--|--|
| Class | `FiveBarHighBreak` |
| Registry name | `five_bar_high_break` |
| Typical StrategyId const | `15` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
Close breaks max high of last 5 bars.

## Exit
Close < min low of prior 3 in window, or +50 bps TP.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
N-bar high breakouts.

