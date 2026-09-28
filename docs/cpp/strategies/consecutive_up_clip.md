# `consecutive_up_clip`

| | |
|--|--|
| Class | `ConsecutiveUpClip` |
| Registry name | `consecutive_up_clip` |
| Typical StrategyId const | `4` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
Momentum clips after `entry_up_bars` (default 8) consecutive higher closes; can scale in on dip+recover.

## Exit
TP/stop bps vs first fill; last-hour red close flattens; adds gated earlier than entries.

## Sizing / session
Clip size from `clip_paise/price`. No new entries ≥ **14:30**; no adds ≥ **13:00**.

## When to fetch
Clip / scale-in / consecutive-up patterns.

