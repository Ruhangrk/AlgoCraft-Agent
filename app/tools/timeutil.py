"""IST session calendar helpers ↔ UTC epoch nanoseconds.

Matches AlgoCraft-UI `istDateToNs`:
- day start = 00:00:00 IST
- day end   = 23:59:00 IST
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
_NS_PER_SEC = 1_000_000_000

# NSE cash equity session close (approx) — used to decide if "today" is still open.
_NSE_CLOSE = time(15, 30)


def _parse_ymd(ymd: str) -> date:
    try:
        return date.fromisoformat(ymd.strip())
    except ValueError as exc:
        raise ValueError(f"date must be YYYY-MM-DD, got {ymd!r}") from exc


def ist_day_start_ns(ymd: str) -> int:
    """IST midnight of `ymd` as UTC epoch nanoseconds."""
    d = _parse_ymd(ymd)
    dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=IST)
    return int(dt.timestamp() * _NS_PER_SEC)


def ist_day_end_ns(ymd: str) -> int:
    """IST 23:59:00 of `ymd` as UTC epoch nanoseconds (UI / AlgoCraft convention)."""
    d = _parse_ymd(ymd)
    dt = datetime(d.year, d.month, d.day, 23, 59, 0, tzinfo=IST)
    return int(dt.timestamp() * _NS_PER_SEC)


def ns_to_ist_ymd(ns: int) -> str:
    """Epoch nanoseconds → civil YYYY-MM-DD in IST."""
    dt = datetime.fromtimestamp(ns / _NS_PER_SEC, tz=IST)
    return dt.date().isoformat()


def ist_now() -> datetime:
    return datetime.now(tz=IST)


def is_nse_weekday(d: date) -> bool:
    return d.weekday() < 5  # Mon–Fri (holidays not calendared in v1)


def last_closed_session_date(*, now: datetime | None = None) -> date:
    """Most recent Mon–Fri session that is already closed (or a past weekday)."""
    now = now or ist_now()
    d = now.date()
    # If today is a weekday and session still open, treat yesterday as last closed.
    if is_nse_weekday(d) and now.timetz().replace(tzinfo=None) < _NSE_CLOSE:
        d = d - timedelta(days=1)
    while not is_nse_weekday(d):
        d = d - timedelta(days=1)
    return d


def last_n_session_days(n: int, *, now: datetime | None = None) -> list[str]:
    """Last `n` NSE weekdays ending at last closed session, as YYYY-MM-DD (oldest→newest)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    d = last_closed_session_date(now=now)
    days: list[date] = []
    while len(days) < n:
        if is_nse_weekday(d):
            days.append(d)
        d = d - timedelta(days=1)
    days.reverse()
    return [x.isoformat() for x in days]


def session_range_ns(from_ymd: str, to_ymd: str) -> tuple[int, int]:
    """from_ns (IST midnight from) and to_ns (IST 23:59 to) for a backtest window."""
    return ist_day_start_ns(from_ymd), ist_day_end_ns(to_ymd)
