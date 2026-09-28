# `opening_range_breakout`

| | |
|--|--|
| Class | `OpeningRangeBreakout` |
| Registry name | `opening_range_breakout` |
| Typical StrategyId const | `3` (local; router may reassign) |
| Indicators | none |
| Resolution / mode | OneMin / MIS |

## Idea
Build opening range over first `orb_bars` (default 3), buy first close above OR high (one entry/day).

## Exit
No sell logic in current code (holds). Agent codegen should still add risk exits if proposing variants.

## Sizing / session
`order_qty`. OR built at session open.

## When to fetch
ORB / opening-range breakout ideas.

