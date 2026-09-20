"""Parse football-data.co.uk season CSVs into the canonical schema.

Handles the two column-schema eras (D8): the `Bb`-prefixed aggregates used through
2018/19, and the flat `Avg`/`Max` columns plus the full closing (`C`) suite from
2019/20 on. Per D5 we care about Bet365 (`B365*`, the price taken), Pinnacle
(`PS*` pre-match, `PSC*` closing — the CLV reference), and `Avg*` as an optimistic
bound; `Max*` is deliberately not extracted (best price in hindsight, unrealizable).

Pure functions over a raw DataFrame — the network fetch + cache live separately so
this stays offline-testable.
"""

from __future__ import annotations

import codecs
import io
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd

from matchscout.data import schema
from matchscout.data.schema import Market, MatchStatus, Selection, validate_matches, validate_odds

# Canonical competition == football-data.co.uk division code, for the Top-5 first tiers.
DIVISIONS: dict[str, str] = {
    "E0": "E0",  # England — Premier League
    "SP1": "SP1",  # Spain — La Liga
    "D1": "D1",  # Germany — Bundesliga
    "I1": "I1",  # Italy — Serie A
    "F1": "F1",  # France — Ligue 1
}

BASE_URL = "https://www.football-data.co.uk/mmz4281"
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"


def season_code(date) -> str:
    """The football-data.co.uk season code covering `date`, e.g. 2026-09-20 -> "2627".

    A season spans August to May, so the unattended pipeline must not need editing every
    August: months 7-12 belong to the season starting that year, months 1-6 to the one before.
    """
    ts = pd.Timestamp(date)
    start = ts.year if ts.month >= 7 else ts.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def previous_season_code(season: str) -> str:
    """The code of the season before `season` ("2627" -> "2526")."""
    start = int(season[:2])
    return f"{(start - 1) % 100:02d}{start % 100:02d}"


def season_url(season: str, div: str) -> str:
    """URL for one season-division CSV, e.g. .../mmz4281/2324/E0.csv."""
    return f"{BASE_URL}/{season}/{div}.csv"


@dataclass(frozen=True)
class _OddsSpec:
    book: str
    is_closing: bool
    market: str
    columns: dict[str, str]  # canonical selection -> raw column name


_H, _D, _A = Selection.HOME.value, Selection.DRAW.value, Selection.AWAY.value
_OV, _UN = Selection.OVER.value, Selection.UNDER.value
_1X2, _OU = Market.ONE_X_TWO.value, Market.OVER_UNDER_25.value

# Flat era (2019/20+): B365/PS/Avg pre-match + full closing suite. Note Pinnacle O/U
# uses the `P`/`PC` prefix, not `PS`/`PSC`.
_FLAT_SPECS: list[_OddsSpec] = [
    _OddsSpec("B365", False, _1X2, {_H: "B365H", _D: "B365D", _A: "B365A"}),
    _OddsSpec("B365", True, _1X2, {_H: "B365CH", _D: "B365CD", _A: "B365CA"}),
    _OddsSpec("PS", False, _1X2, {_H: "PSH", _D: "PSD", _A: "PSA"}),
    _OddsSpec("PS", True, _1X2, {_H: "PSCH", _D: "PSCD", _A: "PSCA"}),
    _OddsSpec("Avg", False, _1X2, {_H: "AvgH", _D: "AvgD", _A: "AvgA"}),
    _OddsSpec("Avg", True, _1X2, {_H: "AvgCH", _D: "AvgCD", _A: "AvgCA"}),
    _OddsSpec("B365", False, _OU, {_OV: "B365>2.5", _UN: "B365<2.5"}),
    _OddsSpec("B365", True, _OU, {_OV: "B365C>2.5", _UN: "B365C<2.5"}),
    _OddsSpec("PS", False, _OU, {_OV: "P>2.5", _UN: "P<2.5"}),
    _OddsSpec("PS", True, _OU, {_OV: "PC>2.5", _UN: "PC<2.5"}),
    _OddsSpec("Avg", False, _OU, {_OV: "Avg>2.5", _UN: "Avg<2.5"}),
    _OddsSpec("Avg", True, _OU, {_OV: "AvgC>2.5", _UN: "AvgC<2.5"}),
]

# Bb era (<=2018/19): B365/PS pre-match, PSC closing (1X2 only), Bb* aggregates.
# No O/U closing, no B365 O/U in this era.
_BB_SPECS: list[_OddsSpec] = [
    _OddsSpec("B365", False, _1X2, {_H: "B365H", _D: "B365D", _A: "B365A"}),
    _OddsSpec("PS", False, _1X2, {_H: "PSH", _D: "PSD", _A: "PSA"}),
    _OddsSpec("PS", True, _1X2, {_H: "PSCH", _D: "PSCD", _A: "PSCA"}),
    _OddsSpec("Avg", False, _1X2, {_H: "BbAvH", _D: "BbAvD", _A: "BbAvA"}),
    _OddsSpec("Avg", False, _OU, {_OV: "BbAv>2.5", _UN: "BbAv<2.5"}),
]


def _parse_dates(s: pd.Series) -> pd.Series:
    """Parse football-data dates with the file's single format — 4-digit year for
    2019/20+ files, 2-digit for older — so parsing is deterministic and warning-free."""
    nonnull = s.dropna().astype(str)
    sample = nonnull.iloc[0] if not nonnull.empty else ""
    fmt = "%d/%m/%Y" if len(sample.split("/")[-1]) == 4 else "%d/%m/%y"
    return pd.to_datetime(s, format=fmt, errors="coerce")


def _era_specs(columns: pd.Index) -> list[_OddsSpec]:
    """Flat era iff the flat `AvgH` aggregate exists; else Bb era (`BbAvH`)."""
    return _FLAT_SPECS if "AvgH" in columns else _BB_SPECS


def _make_ids(
    competition: str, season: str, date: pd.Series, home: pd.Series, away: pd.Series
) -> pd.Series:
    d = date.dt.strftime("%Y%m%d")
    prefix = f"{competition}:{season}:"
    return prefix + d + ":" + home.astype(str) + ":" + away.astype(str)


def parse(raw: pd.DataFrame, competition: str, season: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse one raw season CSV frame into canonical (matches, odds) frames.

    `timestamp_known` is left NaT here; imputing it (kickoff - N h) is the D7 task.
    `kickoff_utc` is left NaT because football-data.co.uk gives local time, not UTC;
    the naive local kickoff goes into `timestamp_event`.
    """
    raw = raw.copy()
    date = _parse_dates(raw["Date"])
    event = date
    if "Time" in raw.columns:
        times = raw["Time"].astype(str).str.strip()
        has_time = times.str.fullmatch(r"\d{1,2}:\d{2}")
        combined = pd.to_datetime(
            date.dt.strftime("%Y-%m-%d") + " " + times,
            format="%Y-%m-%d %H:%M",
            errors="coerce",
        )
        event = combined.where(has_time, date)
    match_id = _make_ids(competition, season, date, raw["HomeTeam"], raw["AwayTeam"])

    home_goals = pd.to_numeric(raw["FTHG"], errors="coerce").astype("Int64")
    away_goals = pd.to_numeric(raw["FTAG"], errors="coerce").astype("Int64")
    played = home_goals.notna() & away_goals.notna()
    status = pd.Series(MatchStatus.SCHEDULED.value, index=raw.index)
    status[played] = MatchStatus.PLAYED.value

    matches = pd.DataFrame(
        {
            "match_id": match_id,
            "competition": competition,
            "season": season,
            "date": date,
            "kickoff_utc": pd.NaT,
            "home": raw["HomeTeam"].astype(str),
            "away": raw["AwayTeam"].astype(str),
            "ft_home_goals": home_goals,
            "ft_away_goals": away_goals,
            "status": status,
            "timestamp_event": event,
            "timestamp_known": pd.NaT,
        }
    )

    odds = _build_odds(raw, match_id, _era_specs(raw.columns))
    return validate_matches(matches), validate_odds(odds)


def _build_odds(raw: pd.DataFrame, match_id: pd.Series, specs: list[_OddsSpec]) -> pd.DataFrame:
    blocks = []
    for spec in specs:
        if not all(col in raw.columns for col in spec.columns.values()):
            continue
        for selection, col in spec.columns.items():
            odds_val = pd.to_numeric(raw[col], errors="coerce")
            block = pd.DataFrame(
                {
                    "match_id": match_id,
                    "market": spec.market,
                    "selection": selection,
                    "book": spec.book,
                    "odds": odds_val,
                    "is_closing": spec.is_closing,
                    "collected_at": pd.NaT,
                }
            )
            # Drop missing (NaN) and malformed (<=1.0) decimal odds rather than crash.
            blocks.append(block[block["odds"] > 1.0])
    if not blocks:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in schema.ODDS_COLUMNS})
    return pd.concat(blocks, ignore_index=True)


def _read_csv(content: bytes) -> pd.DataFrame:
    # football-data.co.uk CSVs are latin-1 encoded and often carry trailing blank columns.
    # Some files (the fixtures feed, current-season files) additionally start with a UTF-8 BOM,
    # which latin-1 would decode into the first column's name and make `Div` unfindable.
    return pd.read_csv(io.BytesIO(content.removeprefix(codecs.BOM_UTF8)), encoding="latin-1")


def _get_with_retry(
    client: httpx.Client, url: str, retries: int, sleep: Callable[[float], None]
) -> bytes:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < retries - 1:
                sleep(2.0**attempt)
    raise RuntimeError(f"failed to fetch {url} after {retries} attempts") from last_exc


def fetch_raw(
    season: str,
    div: str,
    cache_dir: Path,
    *,
    client: httpx.Client | None = None,
    refresh: bool = False,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Return the raw season CSV as a DataFrame, read-through cached under `cache_dir`.

    Raw CSVs are cached (and gitignored) under `.cache/football_data_co_uk/`; they are
    NOT redistributable, so they never leave the cache. `client` is injectable so tests
    use an `httpx.MockTransport` and never hit the network.
    """
    path = Path(cache_dir) / "football_data_co_uk" / season / f"{div}.csv"
    if path.exists() and not refresh:
        return _read_csv(path.read_bytes())

    owns_client = client is None
    client = client or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        content = _get_with_retry(client, season_url(season, div), retries, sleep)
    finally:
        if owns_client:
            client.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return _read_csv(content)


def parse_fixtures(
    raw: pd.DataFrame, competition: str, season: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the upcoming-fixtures feed into canonical (matches, odds) for one competition.

    The feed is one file for every division, with the result columns simply absent — so the
    rows are added as missing and `parse` classifies every fixture as `scheduled`. The closing
    (`C`) columns exist but are empty until the match is played; `_build_odds` drops them, so a
    fixture never carries an invented closing price.
    """
    div = raw[raw["Div"] == DIVISIONS[competition]].copy()
    for column in ("FTHG", "FTAG"):
        if column not in div.columns:
            div[column] = pd.NA
    return parse(div, competition, season)


def fetch_fixtures_raw(
    cache_dir: Path,
    *,
    run_date,
    client: httpx.Client | None = None,
    refresh: bool = False,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Fetch the upcoming-fixtures CSV (all divisions), cached per run date.

    This file is what makes a key-free forward loop possible: the season CSVs carry played
    matches only — verified 2026-09-20, the live 2026/27 E0 file had zero unplayed rows — while
    this one carries the next few days of fixtures WITH pre-match prices. It is volatile (rows
    disappear as matches play), so the cache is keyed by the run date, never by season.
    """
    stamp = pd.Timestamp(run_date).strftime("%Y%m%d")
    path = Path(cache_dir) / "football_data_co_uk" / "fixtures" / f"{stamp}.csv"
    if path.exists() and not refresh:
        return _read_csv(path.read_bytes())

    owns_client = client is None
    client = client or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        content = _get_with_retry(client, FIXTURES_URL, retries, sleep)
    finally:
        if owns_client:
            client.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return _read_csv(content)


class FootballDataCoUkFixtures:
    """FixtureProvider over the upcoming-fixtures feed (pre-match prices, no results).

    One HTTP fetch serves every competition of a run: the raw frame is fetched once, cached on
    disk per run date, and sliced per division.
    """

    def __init__(
        self, cache_dir: Path, *, run_date, client: httpx.Client | None = None
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.run_date = run_date
        self._client = client
        self._raw: pd.DataFrame | None = None

    def _load_raw(self) -> pd.DataFrame:
        if self._raw is None:
            self._raw = fetch_fixtures_raw(
                self.cache_dir, run_date=self.run_date, client=self._client
            )
        return self._raw

    def fetch_upcoming(
        self, competition: str, season: str
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if competition not in DIVISIONS:
            raise KeyError(f"unknown competition {competition!r}; known: {sorted(DIVISIONS)}")
        return parse_fixtures(self._load_raw(), competition, season)


class FootballDataCoUk:
    """MatchProvider + OddsProvider backed by cached football-data.co.uk season CSVs."""

    def __init__(self, cache_dir: Path, *, client: httpx.Client | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self._client = client

    def _load(self, competition: str, season: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        if competition not in DIVISIONS:
            raise KeyError(f"unknown competition {competition!r}; known: {sorted(DIVISIONS)}")
        raw = fetch_raw(season, DIVISIONS[competition], self.cache_dir, client=self._client)
        return parse(raw, competition, season)

    def fetch_matches(self, competition: str, season: str) -> pd.DataFrame:
        return self._load(competition, season)[0]

    def fetch_odds(self, competition: str, season: str) -> pd.DataFrame:
        return self._load(competition, season)[1]
