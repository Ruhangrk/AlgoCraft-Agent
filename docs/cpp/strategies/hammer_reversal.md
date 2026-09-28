# `hammer_reversal`

| | |
|--|--|
| Class | `HammerReversal` |
| Registry name | `hammer_reversal` |
| Typical StrategyId const | `20` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
≥2 red bars then hammer geometry (long lower wick, close in upper third, small upper wick).

## Exit
+40 bps TP or −30 bps SL vs buy fill (`on_fill` stores entry).

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**. Pure price-action template.

## When to fetch
Hammer / wick reversal codegen reference.

