# Strategy interface

Headers: `algocraft/strategies/strategy.hpp`.

## Class contract
Every strategy is `final : public Strategy` in namespace `algocraft` and implements:

```cpp
void configure(const StrategyConfig& config, IndicatorLibrary& lib) override;
void on_bar(const BarEvent& bar, const PortfolioView& portfolio,
            std::vector<OrderIntent>& out) override;
void on_fill(const FillEvent& fill) override;
void on_order_update(const OrderUpdate& update) override;  // often empty {}
bool should_exit() const override;                         // usually false
StrategyMetadata metadata() const override;
```

Engine calls `configure` once, then `on_bar` each bar (indicators already updated), then `on_fill` / `on_order_update` as events arrive. Push intents onto `out`; do not place orders any other way.

## StrategyMetadata
```cpp
struct StrategyMetadata {
  std::string name;                 // MUST equal registry key / snake name
  std::string version{"1.0.0"};
  TradingMode trading_mode{TradingMode::Mis};
  BarResolution required_resolution{BarResolution::OneMin};
  std::vector<std::string> required_indicators{};  // e.g. {"EMA"}
};
```

## StrategyConfig (engine-provided knobs)
Common fields strategies may read (do not invent new config fields the engine will not set):

- `symbol_id`, `order_qty`
- `ema_fast`, `ema_slow`, `rsi_period`, `orb_bars`, `vwap_dev_paise`
- `entry_up_bars`, `add_up_bars`
- `take_profit_bps`, `stop_bps`, `add_max_dip_bps`
- `clip_paise`, `alloc_paise`, `sma_period`

Store a copy in `configure`: `config_ = config;`.

## Lifecycle rules
1. In `configure`: bind indicators via `lib.get<...>(...)`; reset private state.
2. In `on_bar`: filter symbol/resolution; check session gates; manage exits before entries; append 0+ intents.
3. In `on_fill`: record entry price / clear on sell if you need TP/SL.
4. `should_exit()`: container-level bail; prefer `false` unless you truly need forced unwind.
5. `metadata().name` must match the snake_case strategy name used in compile/promote and registry.
