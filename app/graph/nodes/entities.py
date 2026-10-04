"""Natural-language entity helpers (tickers, strategies, dates, intent cues)."""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

# NSE-style tickers plus M&M / BAJAJ-AUTO style symbols
_TICKER_RE = re.compile(r"\b([A-Z]{1,12}(?:[&.-][A-Z0-9]{1,12})?)\b")
_TICKER_LOOSE_RE = re.compile(
    r"\b([A-Za-z]{1,12}(?:[&._-][A-Za-z0-9]{1,12})?)\b"
)
_STRATEGY_LIKE_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")
_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+"
    r"(\d{2,4})\b",
    re.I,
)
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

_MONTH = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_SKIP_TICKERS = frozenset(
    {
        "POST",
        "GET",
        "HTTP",
        "API",
        "IST",
        "NSE",
        "LLM",
        "HI",
        "OK",
        "YES",
        "NO",
        "THE",
        "AND",
        "FOR",
        "YOU",
        "SAID",
        "JUST",
        "WHAT",
        "WHEN",
        "WHERE",
        "THIS",
        "THAT",
        "WITH",
        "FROM",
        "HAVE",
        "WILL",
        "CAN",
        "NOT",
        "ARE",
        "WAS",
        "BUT",
        "ALL",
        "ANY",
        "HOW",
        "WHY",
        "WHO",
        "DID",
        "DOES",
        "AGENT",
        "MIS",
        "SMA",
        "EMA",
        "RSI",
        "ORB",
        "VWAP",
        "SEPT",
        "SEP",
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "JUN",
        "JUL",
        "AUG",
        "OCT",
        "NOV",
        "DEC",
    }
)

# Common backtest misspellings / stems
_BACKTEST_CUES = (
    "backtest",
    "back test",
    "back-test",
    "backest",
    "bactest",
    "bakctest",
    "backtst",
    "backtes",
    "baktetest",
    "simulate",
    "simulation",
    "paper test",
    "papertrade",
)


def normalize_ticker(raw: str) -> str:
    t = raw.strip().upper().replace("_", "&").replace(".", "&")
    # BAJAJ-AUTO style keep hyphen
    if "-" in raw and "&" not in raw:
        t = raw.strip().upper()
    return t


def extract_tickers(text: str) -> list[str]:
    found: list[str] = []
    for m in _TICKER_RE.findall(text):
        t = normalize_ticker(m)
        if t in _SKIP_TICKERS or len(t) < 2:
            continue
        if t not in found:
            found.append(t)
    # lowercase m&m etc.
    for m in _TICKER_LOOSE_RE.findall(text):
        if not any(c in m for c in "&._-"):
            continue
        t = normalize_ticker(m)
        if t in _SKIP_TICKERS or len(t) < 2:
            continue
        if t not in found:
            found.append(t)
    return found


def extract_strategy_likes(text: str) -> list[str]:
    return list(dict.fromkeys(_STRATEGY_LIKE_RE.findall(text.lower())))


def match_catalog_name(text: str, candidates: list[str]) -> str | None:
    lower = text.lower()
    for name in sorted(candidates, key=len, reverse=True):
        if name.lower() in lower:
            return name
    # fuzzy token match against candidates
    tokens = set(re.findall(r"[a-z0-9_&]+", lower))
    best: str | None = None
    best_score = 0.0
    for name in candidates:
        n = name.lower()
        if n in tokens:
            return name
        for tok in tokens:
            if len(tok) < 4:
                continue
            score = SequenceMatcher(None, tok, n).ratio()
            if score > best_score and score >= 0.86:
                best_score = score
                best = name
    return best


def looks_like_backtest(text: str) -> bool:
    lower = text.lower()
    if any(c in lower for c in _BACKTEST_CUES):
        return True
    # "with strategy X" + ticker-ish often means backtest
    if re.search(r"\bwith\s+strateg", lower) and (
        extract_tickers(text) or extract_strategy_likes(text)
    ):
        return True
    # fuzzy single-token near "backtest"
    for tok in re.findall(r"[a-z\-]+", lower):
        if 5 <= len(tok) <= 12:
            if SequenceMatcher(None, tok, "backtest").ratio() >= 0.72:
                return True
    return False


def parse_user_date(text: str, *, default_year: int | None = None) -> str | None:
    """Return YYYY-MM-DD if user named a calendar day, else None."""
    iso = _ISO_DATE_RE.search(text)
    if iso:
        return iso.group(1)
    m = _DATE_RE.search(text)
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTH[m.group(2).lower()]
    year = int(m.group(3))
    if year < 100:
        year += 2000
    try:
        return date(year, mon, day).isoformat()
    except ValueError:
        return None


def looks_like_discuss(text: str) -> bool:
    lower = text.lower()
    cues = (
        "discuss",
        "explain",
        "compare",
        "what is",
        "how does",
        "tell me about",
        "idea for",
        "brainstorm",
        "pros and cons",
        "list strateg",
        "what strateg",
        "research",
        "walk me through",
        "break down",
        "lets discuss",
        "let's discuss",
        "lets talk",
        "let's talk",
    )
    if any(c in lower for c in cues):
        return True
    # "<strategy_name> … discuss/this" covered by discuss word;
    # bare "lets talk about two_consecutive_bars"
    if extract_strategy_likes(text) and any(
        w in lower for w in ("this", "that", "about", "talk", "mean")
    ):
        return True
    return False


@lru_cache(maxsize=1)
def local_strategy_names() -> tuple[str, ...]:
    """Strategy ids with docs under docs/cpp/strategies/ (excl. INDEX)."""
    try:
        from app.config import REPO_ROOT
    except Exception:  # noqa: BLE001
        return ()
    root = Path(REPO_ROOT) / "docs" / "cpp" / "strategies"
    if not root.is_dir():
        return ()
    names = sorted(
        p.stem for p in root.glob("*.md") if p.stem.lower() != "index"
    )
    return tuple(names)


def resolve_strategy_mention(
    text: str,
    catalog: list[str] | None = None,
    *,
    topic: str | None = None,
) -> str | None:
    """Best strategy id from message/topic against catalog + local docs."""
    pool: list[str] = []
    for src in (catalog or [], list(local_strategy_names())):
        for n in src:
            if n not in pool:
                pool.append(n)
    hit = match_catalog_name(text, pool)
    if hit:
        return hit
    if topic:
        hit = match_catalog_name(topic, pool)
        if hit:
            return hit
        if topic in pool:
            return topic
    for like in extract_strategy_likes(text):
        hit = match_catalog_name(like, pool)
        if hit:
            return hit
        if like in pool:
            return like
    return None
