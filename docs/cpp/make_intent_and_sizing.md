# make_intent and sizing

## make_intent
Header: `algocraft/strategies/make_intent.hpp`.

```cpp
OrderIntent make_intent(StrategyId strategy_id, SymbolId symbol_id, Side side,
                        Quantity qty, Price price = {});
```

- Defaults to `OrderType::Market`.
- Pass `price` only for limit/stop-style intents if you set `type` yourself (advanced; prefer Market).
- Always use configured `config_.symbol_id` and your private `StrategyId` constant.

```cpp
out.push_back(make_intent(kSid, config_.symbol_id, Side::Buy, qty));
out.push_back(make_intent(kSid, config_.symbol_id, Side::Sell, pf.position));
```

Flatten with **full position**: `Side::Sell` + `pf.position` (or measured long qty), not a guessed size.

## OrderIntent fields
`strategy_id`, `symbol_id`, `side`, `quantity`, `type`, `price`.

Multiple intents in one `on_bar` are applied **in order** (e.g. sell then buy same bar works on hist sync fills).

## position_for_capital
Header: `algocraft/routing/position_sizer.hpp`.

```cpp
Quantity position_for_capital(Capital cap, Price px, int leverage = 5);
```

- Uses ~95% of `cap * leverage / price`.
- Returns at least 1 share if price/cap positive; guard `qty.shares() > 0` before buy.
- Typical pattern: risk a **fraction** of cash, e.g. 40%:

```cpp
const auto qty = position_for_capital(
    Capital::from_paise(pf.cash.paise() * 40 / 100), bar.close, 1);
```

Use `leverage=1` unless you intentionally want MIS leverage sizing.

## Qty pitfalls
- Do **not** size with full container capital as market qty when price × shares ≈ cash — orders get rejected / blocked and you get zero churn.
- For smoke tests, fixed `Quantity::from_shares(1)` is fine.
- Prefer `config_.order_qty` only when the router/backtest sets a sensible clip; otherwise fraction-of-cash or 1 share.
