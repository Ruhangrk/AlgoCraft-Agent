# `default_router`

| | |
|--|--|
| Class | `DefaultRouter` |
| Eval sessions | **14** |
| Selection | Every pair with **PnL > 0** (no top-N cap) |
| Capital | Equal split across winners |

## Defaults
**Tickers (10):** RELIANCE, INFY, TCS, HDFCBANK, ICICIBANK, SBIN, BHARTIARTL, ITC, LT, HINDUNILVR

**Strategies:** `ema_crossover`, `vwap_reversion`, `consecutive_up_clip`

## SMA warmup
Yes — if winning strategy metadata needs `"SMA"`.

## When to use
Baseline hist/live routing on liquid names with classic trend/VWAP/clip set.
