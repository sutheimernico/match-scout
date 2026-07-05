"""Provider seam: source-agnostic interfaces for match + odds data.

Concrete providers (football-data.co.uk, football-data.org) implement these; the
`FakeProvider` in `fakes.py` backs the test suite so no live network is ever hit.
`@runtime_checkable` lets tests assert conformance structurally without inheritance.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class MatchProvider(Protocol):
    def fetch_matches(self, competition: str, season: str) -> pd.DataFrame:
        """Return canonical `matches` rows for one competition-season (may be empty)."""
        ...


@runtime_checkable
class OddsProvider(Protocol):
    def fetch_odds(self, competition: str, season: str) -> pd.DataFrame:
        """Return canonical `odds` rows for one competition-season (may be empty)."""
        ...
