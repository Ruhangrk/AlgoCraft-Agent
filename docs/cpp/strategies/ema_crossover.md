# `ema_crossover`

| | |
|--|--|
| Class | `EmaCrossover` |
| Registry name | `ema_crossover` |
| Typical StrategyId const | `1` (local; router may reassign) |
| Indicators | EMA fast/slow |
| Resolution / mode | OneMin / MIS |

## Idea
Bullish EMA cross when flat; bearish cross exits full position.

## Indicators
`lib.get<Ema>(symbol, OneMin, config.ema_fast)` and `ema_slow` (defaults 9/21).

## Entry
When previous fast≤slow and now fast>slow, and `position == 0`.

## Exit
When previous fast≥slow and now fast<slow, and long → sell `pf.position`.

## Sizing / session
Uses `config_.order_qty`. No IST cutoff.

## When to fetch
Trend crossover templates; indicator bind/ready pattern.

