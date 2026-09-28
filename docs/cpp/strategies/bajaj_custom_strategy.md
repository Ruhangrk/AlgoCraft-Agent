# `bajaj_custom_strategy`

| | |
|--|--|
| Class | `BajajCustomStrategy` |
| Registry name | `bajaj_custom_strategy` |
| Typical StrategyId const | `5` (local; router may reassign) |
| Indicators | RSI+VWAP |
| Resolution / mode | OneMin / MIS |

## Idea
Intraday dip buy: RSI oversold under VWAP band, one entry/day in morning window.

## Indicators
RSI(`rsi_period`, default 14) + VWAP.

## Entry
09:30–13:00 IST: RSI < 32 and close ≤ VWAP − 25 bps; once per day.

## Exit
TP/SL ~30 bps, RSI ≥ 60, close ≥ VWAP, or flatten ≥ **14:30**.

## Sizing
~40% cash as margin → `position_for_capital(..., leverage=5)`.

## When to fetch
RSI+VWAP combo / timed session windows.

