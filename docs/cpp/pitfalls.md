# Codegen pitfalls

Avoid these; they cause compile failures, zero fills, or bad live behavior.

1. **Float money** — never `double` rupees for OHLC math; use `.paise()` ints (or bps integer formulas).
2. **Wrong include path** — must be `#include "algocraft/strategies/<name>.hpp"` matching snake name.
3. **metadata.name ≠ name** — registry/compile/promote break silently for users.
4. **Invalid name** — must match `^[a-z][a-z0-9_]{0,63}$`.
5. **Full-capital market qty** — `order_qty` sized to entire cash → rejects / no churn. Prefer 1 share or `position_for_capital` on a cash fraction.
6. **No symbol/resolution filter** — strategy fires on every bar in multiplexed feeds.
7. **Entries after cutoff with no flatten** — MIS risk; always allow exits after last-entry minute.
8. **Using indicators without ready()** — garbage crossover signals.
9. **Updating indicators in strategy** — container already updates; do not call update.
10. **Promoting without human OK** — agent policy + product rule; compile only until confirmed.
11. **Expecting activate to load code** — still need rebuild + restart `serve`.
12. **Inventing router codegen** — v1 agent APIs only support `kind=strategy`.
13. **Wall-clock / string times in C++** — use `ist_minute_of_day` / nanos.
14. **Sell qty ≠ position** — flatten with `pf.position`, not a stale stored qty unless you track carefully.
15. **Ignoring compile `log`** — fix from compiler stderr; do not reshuffle randomly past 5 attempts.
