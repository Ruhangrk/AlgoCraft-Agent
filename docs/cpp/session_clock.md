# Session clock (IST)

Header: `algocraft/domain/session_clock.hpp`.

## Constants
- `kIstOffsetNs` — +5:30 in nanoseconds
- `kNanosPerDay`, `kNanosPerMinute`

## Helpers
```cpp
int ist_minute_of_day(Timestamp ts);   // minutes since IST midnight
bool nse_regular_hours(Timestamp ts);  // [09:15, 15:30) IST
```

Examples:
- 09:15 IST → `9*60+15`
- 14:30 IST → `14*60+30`
- 15:15 IST → `15*60+15`
- 15:30 IST → outside regular hours (`nse_regular_hours` false)

## Strategy patterns
**Last entry cutoff** (common long strategies: no new entries after 14:30 IST):

```cpp
constexpr int kLastEntryMin = 14 * 60 + 30;
if (ist_minute_of_day(bar.timestamp) >= kLastEntryMin) {
  // still allow exits / flatten
  return;
}
```

**MIS flatten near close** (`live_run_testing` uses 15:15): after cutoff, sell open position, skip new buys.

**Session day reset** (state that must not leak across days):

```cpp
const auto day = bar.timestamp.nanos() / kNanosPerDay;
if (day != session_day_) {
  session_day_ = day;
  // reset streaks / day flags
}
```

## Calendar note
NSE holidays / session days live in `session_calendar.hpp` (`is_nse_session_day`, `ist_at`). Strategies usually only need `ist_minute_of_day`; agent Python tools use Asia/Kolkata for `from_ns` / `to_ns` / `anchor_date`.
