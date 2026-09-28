"""Unit tests for IST ↔ nanos helpers."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.tools.timeutil import (
    IST,
    ist_day_end_ns,
    ist_day_start_ns,
    last_closed_session_date,
    last_n_session_days,
    ns_to_ist_ymd,
    session_range_ns,
)


def test_known_ist_day_midnight_and_eod() -> None:
    # Matches AlgoCraft-UI istDateToNs / zoneinfo Asia/Kolkata
    start = ist_day_start_ns("2024-01-15")
    assert start == 1_705_257_000_000_000_000
    end = ist_day_end_ns("2024-01-15")
    assert end == 1_705_343_340_000_000_000
    assert ns_to_ist_ymd(start) == "2024-01-15"
    assert ns_to_ist_ymd(end) == "2024-01-15"


def test_session_range_ns() -> None:
    lo, hi = session_range_ns("2024-01-15", "2024-01-16")
    assert lo == ist_day_start_ns("2024-01-15")
    assert hi == ist_day_end_ns("2024-01-16")
    assert hi > lo


def test_bad_ymd() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        ist_day_start_ns("15-01-2024")


def test_last_n_session_days_skips_weekend() -> None:
    # Friday 2024-01-19 16:00 IST — session closed; last 5 = Mon–Fri that week
    now = datetime(2024, 1, 19, 16, 0, tzinfo=IST)
    days = last_n_session_days(5, now=now)
    assert days == [
        "2024-01-15",
        "2024-01-16",
        "2024-01-17",
        "2024-01-18",
        "2024-01-19",
    ]


def test_last_closed_excludes_open_today() -> None:
    # Wednesday morning — today still open → last closed is Tuesday
    now = datetime(2024, 1, 17, 10, 0, tzinfo=IST)
    assert last_closed_session_date(now=now).isoformat() == "2024-01-16"
