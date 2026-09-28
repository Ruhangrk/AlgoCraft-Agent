# `top15_week_router`

| | |
|--|--|
| Class | `Top15WeekRouter` |
| Eval sessions | **5** (~1 week) |
| Selection | PnL > 0, then **top 15** by PnL |
| Capital | Equal split among selected |

## Defaults
**Tickers (20):** RELIANCE, INFY, TCS, HDFCBANK, ONGC, COALINDIA, DIVISLAB, PAGEIND, BOSCHLTD, JUBLFOOD, VEDL, MPHASIS, TECHM, WIPRO, CANBK, UNIONBANK, ICICIGI, SAIL, ITC, SBIN

**Strategies:** hammer_reversal, piercing_line_long, morning_star_long, bull_harami_break, three_white_soldiers, dip5_mean_revert, bull_engulf_long, three_red_bounce, two_green_thrust, five_bar_high_break, dip5_mean_revert (listed twice in source), two_consecutive_bars, consecutive_up_clip

## SMA warmup
Yes when strategy needs `"SMA"`.

## When to use
Short-window candlestick / mean-reversion tournament; cap live slots at 15.
