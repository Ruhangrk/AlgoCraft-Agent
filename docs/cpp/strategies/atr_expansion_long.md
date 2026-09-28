# `atr_expansion_long`

| | |
|--|--|
| Class | `AtrExpansionLong` |
| Registry name | `atr_expansion_long` |
| Typical StrategyId const | `25` (local; router may reassign) |
| Indicators | internal ATR |
| Resolution / mode | OneMin / MIS |

## Idea
True range expands ≥ ~1.8× ATR(14) on a green bar (ATR computed inside strategy, not IndicatorLibrary).

## Exit
+1.5× ATR target or −1× ATR stop.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
Volatility expansion breakouts / custom ATR logic.

