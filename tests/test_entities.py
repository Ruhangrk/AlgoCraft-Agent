"""NL entity extraction helpers."""

from __future__ import annotations

from app.graph.nodes.entities import (
    extract_strategy_likes,
    extract_tickers,
    match_catalog_name,
    parse_user_date,
)


def test_labeled_lowercase_ticker_and_spaced_strategy() -> None:
    text = (
        "backtest using these details : Ticker : asianpaint, "
        "strategy : hammer reversal, date : 1st october"
    )
    assert extract_tickers(text) == ["ASIANPAINT"]
    assert "hammer_reversal" in extract_strategy_likes(text)
    assert match_catalog_name(text, ["hammer_reversal", "ema_crossover"]) == "hammer_reversal"
    assert parse_user_date(text, default_year=2025) == "2025-10-01"


def test_uppercase_and_on_lowercase_ticker() -> None:
    assert extract_tickers("backtest hammer_reversal on RELIANCE") == ["RELIANCE"]
    assert extract_tickers("backtest on reliance") == ["RELIANCE"]


def test_date_with_year_still_works() -> None:
    assert parse_user_date("backest M&M for 28th sept 26") == "2026-09-28"
