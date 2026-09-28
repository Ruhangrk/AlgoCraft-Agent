# `open_dump_fade`

| | |
|--|--|
| Class | `OpenDumpFade` |
| Registry name | `open_dump_fade` |
| Typical StrategyId const | `14` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
Fade morning dump: in first ~20 bars, close ≤ day open − 30 bps; once/day.

## Exit
+40 bps TP, −30 bps SL, or force exit ≥ **12:00** IST.

## Sizing / session
40% cash, leverage 1. Morning-only style.

## When to fetch
Open-drive fade / morning dump.

