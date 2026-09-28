# Example patterns (copy structure, not fluff)

## 1) `ema_crossover` — indicators + cross
- `configure`: `lib.get<Ema>(symbol, OneMin, ema_fast/slow)`.
- `on_bar`: wait `ready()`; detect cross vs previous fast>slow; buy `config_.order_qty` when flat; sell full position on cross down.
- `metadata.required_indicators = {"EMA"}`.
- Good template for indicator strategies.

## 2) `hammer_reversal` — pure price action + TP/SL
- No indicators.
- Filter `symbol_id` + `OneMin`.
- Reset streak on session day change (`nanos()/kNanosPerDay`).
- Count red bars; hammer geometry on **paise** OHLC.
- No entries after 14:30 IST; still exits when long.
- Size: `position_for_capital(cash*40/100, close, leverage=1)`.
- `on_fill`: store buy fill paise as entry; clear on sell.
- Exit: ±bps vs entry with integer `c*10000` vs `entry*(10000±bps)`.
- Good template for pattern + risk exits.

## 3) `live_run_testing` — fill churn smoke
- Every bar before 15:15 IST: if long, sell full position then buy 1 share; if flat, buy 1 share.
- Ignores large `order_qty` (fixed 1 share) so capital does not block fills.
- After 15:15: flatten only.
- Use as reference for **intent ordering** and MIS flatten — not as a real alpha strategy.

## Minimal on_bar skeleton
```cpp
void MyStrat::on_bar(const BarEvent& bar, const PortfolioView& pf,
                     std::vector<OrderIntent>& out) {
  if (bar.symbol_id != config_.symbol_id || bar.resolution != BarResolution::OneMin) return;
  if (ist_minute_of_day(bar.timestamp) >= kLastEntryMin) {
    if (pf.position.shares() > 0)
      out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
    return;
  }
  // exits if long ...
  // entries if flat ...
}
```
