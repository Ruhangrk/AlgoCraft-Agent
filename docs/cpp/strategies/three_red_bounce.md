# `three_red_bounce`

| | |
|--|--|
| Class | `ThreeRedBounce` |
| Registry name | `three_red_bounce` |
| Typical StrategyId const | `10` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
After 3 consecutive red 1m bars, fade for a bounce.

## Exit
2 green bars or −40 bps stop vs entry.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
Red-streak bounce / exhaustion fades.

