# Units and core types

All money and time in AlgoCraft strategies use **integers**. Never use floating rupees or wall-clock strings inside strategy logic.

## Money
| Type | Factory | Accessor | Unit |
|------|---------|----------|------|
| `Price` | `Price::from_paise(n)` | `.paise()` | **paise** (₹1 = 100 paise) |
| `Capital` | `Capital::from_paise(n)` | `.paise()` | **paise** |
| `Quantity` | `Quantity::from_shares(n)` | `.shares()` | whole shares |

Examples: ₹250.50 → `25050` paise. ₹10,00,000 capital → `10'00'000'00` paise.

OHLC on bars are `Price`. Fees / cash impacts on fills are `Capital`.

## Time
| Type | Factory | Accessor | Unit |
|------|---------|----------|------|
| `Timestamp` | `Timestamp::from_nanos(n)` | `.nanos()` | UTC epoch **nanoseconds** |

IST = UTC + 5:30. Helpers in `session_clock.hpp` (see `session_clock.md`).  
Day bucketing often uses `bar.timestamp.nanos() / kNanosPerDay`.

## Enums used in intents
- `Side::Buy`, `Side::Sell`
- `OrderType::Market` (default via `make_intent`), also `Limit`, `StopLoss`, `StopLossMarket`
- `OrderStatus`: `Submitted`, `Partial`, `Filled`, `Cancelled`, `Rejected`
- `TradingMode::Mis` (default for generated strategies)
- `BarResolution::OneMin` (default for generated strategies)

## BarEvent (what `on_bar` sees)
- `symbol_id` (`SymbolId`)
- `timestamp` (`Timestamp`)
- `resolution` (`BarResolution`)
- `open`, `high`, `low`, `close` (`Price`)
- `volume` (`Quantity`)

Filter early: wrong `symbol_id` or wrong `resolution` → return.

## IDs
Opaque wrappers: `StrategyId::from(n)`, `SymbolId`, `OrderId`, `ContainerId`, `WorkbookId`.  
Strategy code usually hardcodes a private `StrategyId` constant for intents (existing strategies use distinct ints like 1, 20, 40).
