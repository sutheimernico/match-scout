"""Canonical, source-agnostic schema for the match + odds tables.

Providers return pandas DataFrames conforming to these column sets, so the rest of the
pipeline never sees source-specific column names (football-data.co.uk `B365CH`, etc.).
The validators enforce the honesty-critical invariants at the data boundary — most
importantly that `timestamp_known` never precedes-into-the-future of `timestamp_event`
(no lookahead) and that decimal odds are well-formed.
"""

from __future__ import annotations

from enum import StrEnum

import pandas as pd


class Market(StrEnum):
    ONE_X_TWO = "1x2"
    OVER_UNDER_25 = "ou25"


class Selection(StrEnum):
    HOME = "H"
    DRAW = "D"
    AWAY = "A"
    OVER = "over"
    UNDER = "under"


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    PLAYED = "played"
    VOID = "void"


MATCH_COLUMNS: list[str] = [
    "match_id",
    "competition",
    "season",
    "date",
    "kickoff_utc",
    "home",
    "away",
    "ft_home_goals",
    "ft_away_goals",
    "status",
    "timestamp_event",  # kickoff — audit-only, never used to select/price a bet
    "timestamp_known",  # when the row became knowable — the only time a bet may use
]

ODDS_COLUMNS: list[str] = [
    "match_id",
    "market",
    "selection",
    "book",  # e.g. "B365", "PS", "PSC" (Pinnacle closing), "Avg", "Max"
    "odds",  # decimal
    "is_closing",  # True for closing (`C`) columns; feeds CLV only, never placement
    "collected_at",
]

VALID_MARKETS: set[str] = {m.value for m in Market}
VALID_SELECTIONS: set[str] = {s.value for s in Selection}

MARKET_SELECTIONS: dict[str, set[str]] = {
    Market.ONE_X_TWO.value: {Selection.HOME.value, Selection.DRAW.value, Selection.AWAY.value},
    Market.OVER_UNDER_25.value: {Selection.OVER.value, Selection.UNDER.value},
}


class SchemaError(ValueError):
    """Raised when a DataFrame does not conform to the canonical schema."""


def align_timestamps(dates: pd.Series, reference) -> tuple[pd.Series, pd.Timestamp]:
    """Put a date column and a reference timestamp on the same timezone footing.

    The two free sources disagree: football-data.co.uk is tz-naive local time,
    football-data.org is tz-aware UTC. Comparing one against the other raises instead of
    answering, which would turn every point-in-time guard into a crash rather than a check.
    """
    dates = pd.to_datetime(dates)
    ref = pd.Timestamp(reference)
    tz = dates.dt.tz
    if tz is None:
        return dates, (ref.tz_convert("UTC").tz_localize(None) if ref.tz is not None else ref)
    return dates, (ref.tz_localize(tz) if ref.tz is None else ref.tz_convert(tz))


def validate_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a canonical `matches` frame in place; return it for chaining."""
    _require_columns(df, MATCH_COLUMNS, "matches")
    if df.empty:
        return df

    bad_status = set(df["status"].dropna().unique()) - {s.value for s in MatchStatus}
    if bad_status:
        raise SchemaError(f"matches: invalid status values {sorted(bad_status)}")

    played = df["status"] == MatchStatus.PLAYED.value
    if played.any() and df.loc[played, ["ft_home_goals", "ft_away_goals"]].isna().any().any():
        raise SchemaError("matches: played rows must have both goal columns set")

    # Normalize to UTC so tz-naive (football-data.co.uk local) and tz-aware
    # (football-data.org) timestamps compare cleanly; guard the empty case.
    known = pd.to_datetime(df["timestamp_known"], utc=True, errors="coerce")
    event = pd.to_datetime(df["timestamp_event"], utc=True, errors="coerce")
    both = known.notna() & event.notna()
    if both.any() and (known[both] > event[both]).any():
        raise SchemaError("matches: timestamp_known must be <= timestamp_event (no lookahead)")
    return df


def validate_odds(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a canonical `odds` frame in place; return it for chaining."""
    _require_columns(df, ODDS_COLUMNS, "odds")
    if df.empty:
        return df

    bad_market = set(df["market"].dropna().unique()) - VALID_MARKETS
    if bad_market:
        raise SchemaError(f"odds: invalid market values {sorted(bad_market)}")

    for market, group in df.groupby("market"):
        allowed = MARKET_SELECTIONS.get(str(market), set())
        bad = set(group["selection"].dropna().unique()) - allowed
        if bad:
            raise SchemaError(f"odds: selections {sorted(bad)} invalid for market {market!r}")

    if (df["odds"].dropna() <= 1.0).any():
        raise SchemaError("odds: decimal odds must be > 1.0")
    return df


def _require_columns(df: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise SchemaError(f"{name}: missing columns {missing}")
