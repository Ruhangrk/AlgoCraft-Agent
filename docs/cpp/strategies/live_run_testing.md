# `live_run_testing`

| | |
|--|--|
| Class | `LiveRunTesting` |
| Registry name | `live_run_testing` |
| Typical StrategyId const | `40` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
Smoke churn: every bar buy 1 share; if long, sell full then rebuy same bar.

## Exit / session
After **15:15** IST only flatten; no new buys.

## Sizing
**Fixed 1 share** (ignores large `order_qty`) so capital does not block fills.

## When to fetch
Fill-path / live smoke only — not alpha.

