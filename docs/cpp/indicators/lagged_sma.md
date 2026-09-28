# LaggedSma

| | |
|--|--|
| Class | `LaggedSma` |
| `kTypeName` | `"LAGGED_SMA"` |
| Header | `algocraft/indicators/lagged_sma.hpp` |

## get args
`(SymbolId, BarResolution::OneMin, int period)`

## Semantics
After `update`, `value()` is the mean of the **previous** `period` closes (**excluding** the bar just applied). Compare current close vs that mean for breakout/mean-revert.

## ready
True after enough OneMin closes. Daily warmup does not pollute.
