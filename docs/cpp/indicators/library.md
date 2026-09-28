# IndicatorLibrary

Header: `algocraft/indicators/indicator_library.hpp`.

## Base `Indicator`
Virtual: `update(bar)`, `value()` → `double`, `ready()` → `bool`.

## Engine rule
Container calls `lib.update(bar)` **before** strategy `on_bar`. Strategies must not update indicators.

## get<T>
```cpp
auto& ema = lib.get<Ema>(symbol_id, BarResolution::OneMin, period);
```
- Dedupes by `T::kTypeName:symbol:resolution:args…`
- Returns reference; library owns memory
- Register happens on first `get`

## Strategy usage
1. In `configure`: store pointers from `get<...>`
2. In `on_bar`: `if (!ind->ready()) return;` then use `ind->value()`
