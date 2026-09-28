# Portfolio view and fills

## PortfolioView (`on_bar`)
```cpp
struct PortfolioView {
  Quantity position{};  // net shares for this container/symbol context
  Capital cash{};
};
```

- Flat: `pf.position.shares() == 0`
- Long: `shares() > 0`
- Cash for sizing: `pf.cash.paise()`

Treat as read-only snapshot for this bar.

## FillEvent (`on_fill`)
Key fields: `side`, `filled_qty`, `fill_price`, `fees`, `net_cash_impact`, `timestamp`.

Typical entry tracking:

```cpp
void on_fill(const FillEvent& f) override {
  entry_paise_ = (f.side == Side::Buy) ? f.fill_price.paise() : 0;
}
```

## TP / SL in basis points
Integer math on paise (from `hammer_reversal`):

```cpp
// take profit +40 bps, stop -30 bps vs entry_
if (c * 10000 >= entry_ * (10000 + kTp) ||
    c * 10000 <= entry_ * (10000 - kStop)) {
  out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
}
```

Handle **exits before entries** in `on_bar` when already long.

## OrderUpdate
Often unused (`{}`). Statuses: Submitted / Partial / Filled / Cancelled / Rejected. Do not assume every intent fills; still gate on `pf.position` for state.
