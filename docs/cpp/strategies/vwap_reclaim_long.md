# `vwap_reclaim_long`

| | |
|--|--|
| Class | `VwapReclaimLong` |
| Registry name | `vwap_reclaim_long` |
| Typical StrategyId const | `13` (local; router may reassign) |
| Indicators | VWAP |
| Resolution / mode | OneMin / MIS |

## Idea
Buy when price reclaims VWAP (cross from below to above).

## Exit
Cross back below VWAP.

## Sizing / session
40% cash, leverage 1. No entries ≥ **14:30**.

## When to fetch
VWAP reclaim / cross strategies.

