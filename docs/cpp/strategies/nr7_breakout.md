# `nr7_breakout`

| | |
|--|--|
| Class | `Nr7Breakout` |
| Registry name | `nr7_breakout` |
| Typical StrategyId const | `26` (local; router may reassign) |
| Indicators | internal NR7 |
| Resolution / mode | OneMin / MIS |

## Idea
After narrowest-range-of-7 bar, buy break above NR high (range tracked inside strategy).

## Exit
TP/SL or close < NR low.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
NR7 / narrow-range breakout patterns.

