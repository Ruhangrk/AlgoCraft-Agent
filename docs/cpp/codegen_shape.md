# Generated strategy shape (emit this)

Phase B LLM output must be JSON fields `name`, `class_name`, `hpp`, `cpp` (and `kind: "strategy"`).

## Naming
- `name`: snake_case, regex `^[a-z][a-z0-9_]{0,63}$` (max 64 chars). Example: `my_mean_revert`.
- `class_name`: PascalCase from snake (`MyMeanRevert`). May omit; compiler derives it.
- `metadata().name` **must** equal `name`.

## Header (`hpp`)
```cpp
#pragma once

#include "algocraft/strategies/strategy.hpp"

namespace algocraft {

class MyMeanRevert final : public Strategy {
public:
  void configure(const StrategyConfig&, IndicatorLibrary&) override;
  void on_bar(const BarEvent&, const PortfolioView&, std::vector<OrderIntent>&) override;
  void on_fill(const FillEvent&) override;
  void on_order_update(const OrderUpdate&) override {}
  bool should_exit() const override { return false; }
  StrategyMetadata metadata() const override;

private:
  StrategyConfig config_{};
  // private state...
};

}  // namespace algocraft
```

## Source (`cpp`)
```cpp
#include "algocraft/strategies/my_mean_revert.hpp"

#include "algocraft/domain/bar_resolution.hpp"
#include "algocraft/domain/session_clock.hpp"      // if time gates
#include "algocraft/routing/position_sizer.hpp"    // if sizing
#include "algocraft/strategies/make_intent.hpp"
// indicator headers if used

namespace algocraft {
namespace {
constexpr StrategyId kSid = StrategyId::from(/* pick unused int */);
}
// implement methods...
StrategyMetadata MyMeanRevert::metadata() const {
  return {"my_mean_revert", "1.0.0", TradingMode::Mis, BarResolution::OneMin, {}};
}
}  // namespace algocraft
```

## Includes
- Always: strategy header path `"algocraft/strategies/<name>.hpp"`.
- Intents: `make_intent.hpp`.
- Time: `session_clock.hpp`.
- Size: `position_sizer.hpp`.
- Indicators: concrete headers under `algocraft/indicators/`.

## Do not
- Invent build systems, CMake, or registration code (promote patches those).
- Use floating rupees / wall-clock strings.
- Depend on files outside project `include/`.
- Emit router classes in v1 (`kind` must be `"strategy"`).

## After emit
1. `POST /agent/strategies/compile` until `ok=true` (max 5 attempts; fix from `log`).
2. Human OK → `promote` (catalog `enabled=0`).
3. Human OK → `activate` then rebuild+restart engine (no hot dlopen yet).
