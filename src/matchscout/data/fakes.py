"""In-memory fake provider for deterministic, network-free tests."""

from __future__ import annotations

import pandas as pd

from matchscout.data import schema


class FakeProvider:
    """A MatchProvider + OddsProvider backed by in-memory frames.

    Keyed by (competition, season); returns an empty canonical frame for unknown keys
    and always hands back a copy so callers cannot mutate the fixture.
    """

    def __init__(
        self,
        matches: dict[tuple[str, str], pd.DataFrame] | None = None,
        odds: dict[tuple[str, str], pd.DataFrame] | None = None,
    ) -> None:
        self._matches = matches or {}
        self._odds = odds or {}

    def fetch_matches(self, competition: str, season: str) -> pd.DataFrame:
        df = self._matches.get((competition, season))
        return df.copy() if df is not None else _empty(schema.MATCH_COLUMNS)

    def fetch_odds(self, competition: str, season: str) -> pd.DataFrame:
        df = self._odds.get((competition, season))
        return df.copy() if df is not None else _empty(schema.ODDS_COLUMNS)


class FakeFixtureProvider:
    """A FixtureProvider over in-memory (matches, odds) pairs keyed by (competition, season)."""

    def __init__(
        self, upcoming: dict[tuple[str, str], tuple[pd.DataFrame, pd.DataFrame]] | None = None
    ) -> None:
        self._upcoming = upcoming or {}

    def fetch_upcoming(
        self, competition: str, season: str
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        pair = self._upcoming.get((competition, season))
        if pair is None:
            return _empty(schema.MATCH_COLUMNS), _empty(schema.ODDS_COLUMNS)
        return pair[0].copy(), pair[1].copy()


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in columns})
