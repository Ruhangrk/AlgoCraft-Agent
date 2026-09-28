# `two_consecutive_bars`

| | |
|--|--|
| Class | `TwoConsecutiveBars` |
| Registry name | `two_consecutive_bars` |
| Typical StrategyId const | `6` (local; router may reassign) |
| Indicators | SMA 200DMA |
| Resolution / mode | OneMin / MIS |

## Idea
Only when price above daily 200 SMA: enter on 3 greens or 2 greens with ≥0.25% range thrust.

## Indicators
`Sma` on **OneDay** (`sma_period` default 200). Needs daily SMA warmup (`required_indicators` includes `"SMA"`).

## Exit
3 reds, or 2 reds + fee-aware break-even style exit.

## Sizing / session
~10% of `alloc_paise`/`clip_paise`, leverage 1. No buys ≥ **14:30**.

## When to fetch
Daily regime filter + multi-bar thrust.

