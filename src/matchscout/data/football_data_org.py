"""football-data.org (API v4) provider: Champions League / World Cup fixtures + results.

Free tier (10 req/min): competitions include Champions League (CL), World Cup (WC), European
Championship (EC), and the Top-5 leagues. Auth via the `X-Auth-Token` header. The API has NO
betting odds anywhere, so these competitions run in shadow-mode — the model produces predictions
but no bets are staked (no free odds to settle against). Match times are real UTC (unlike
football-data.co.uk), so they populate `kickoff_utc` directly.

The key is read from FOOTBALL_DATA_API_KEY; if absent the provider raises with guidance so the
pipeline can skip it rather than fabricate data. `client` is injectable so tests never hit the net.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pandas as pd

from matchscout.config import football_data_api_key
from matchscout.data import schema
from matchscout.data.schema import MatchStatus, validate_matches

BASE_URL = "https://api.football-data.org/v4"

# canonical competition -> football-data.org competition code (all on the free tier).
# Leagues are here too so live tips are competition-agnostic: whatever is in season shows up.
COMPETITIONS: dict[str, str] = {
    "CL": "CL",  # UEFA Champions League
    "WC": "WC",  # FIFA World Cup
    "EC": "EC",  # UEFA European Championship
    "PL": "PL",  # Premier League
    "BL1": "BL1",  # Bundesliga
    "SA": "SA",  # Serie A
    "PD": "PD",  # La Liga (Primera Division)
    "FL1": "FL1",  # Ligue 1
}


def _fetch_json(
    code: str,
    season: str,
    cache_dir: Path,
    *,
    api_key: str | None,
    client: httpx.Client | None,
    refresh: bool,
    retries: int,
    sleep: Callable[[float], None],
) -> dict:
    path = Path(cache_dir) / "football_data_org" / f"{code}_{season}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    if not api_key:
        raise RuntimeError(
            "no FOOTBALL_DATA_API_KEY set — cannot fetch football-data.org; "
            "add it to .env (free token from football-data.org) or skip CL/WC."
        )

    owns = client is None
    client = client or httpx.Client(timeout=30.0)
    headers = {"X-Auth-Token": api_key}
    url = f"{BASE_URL}/competitions/{code}/matches?season={season}"
    try:
        for attempt in range(retries):
            resp = client.get(url, headers=headers)
            if resp.status_code == 429 and attempt < retries - 1:
                sleep(6.0 * (attempt + 1))  # free tier: 10 req/min — back off and retry
                continue
            resp.raise_for_status()  # other 4xx/5xx (e.g. season not available) raise immediately
            data = resp.json()
            break
        else:
            raise RuntimeError(f"rate-limited fetching {url} after {retries} attempts")
    finally:
        if owns:
            client.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def _parse(data: dict, competition: str, season: str) -> pd.DataFrame:
    rows = []
    for match in data.get("matches", []):
        home = match["homeTeam"].get("name") or match["homeTeam"].get("shortName") or "?"
        away = match["awayTeam"].get("name") or match["awayTeam"].get("shortName") or "?"
        full_time = match.get("score", {}).get("fullTime", {})
        hg, ag = full_time.get("home"), full_time.get("away")
        finished = match.get("status") == "FINISHED" and hg is not None and ag is not None
        kickoff = pd.to_datetime(match.get("utcDate"), utc=True, errors="coerce")
        rows.append(
            {
                "match_id": f"{competition}:{season}:{match.get('id')}",
                "competition": competition,
                "season": season,
                "date": kickoff,
                "kickoff_utc": kickoff,  # real UTC from the API
                "home": home,
                "away": away,
                "ft_home_goals": hg if finished else None,
                "ft_away_goals": ag if finished else None,
                "status": MatchStatus.PLAYED.value if finished else MatchStatus.SCHEDULED.value,
                "timestamp_event": kickoff,
                "timestamp_known": pd.NaT,
            }
        )
    if not rows:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in schema.MATCH_COLUMNS})
    df = pd.DataFrame(rows)
    df["ft_home_goals"] = pd.to_numeric(df["ft_home_goals"], errors="coerce").astype("Int64")
    df["ft_away_goals"] = pd.to_numeric(df["ft_away_goals"], errors="coerce").astype("Int64")
    return validate_matches(df)


class FootballDataOrg:
    """MatchProvider for CL / WC / EC fixtures + results (no odds — shadow-mode competitions)."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self._api_key = api_key or football_data_api_key()
        self._client = client

    def fetch_matches(
        self, competition: str, season: str, *, refresh: bool = False
    ) -> pd.DataFrame:
        if competition not in COMPETITIONS:
            raise KeyError(f"unknown competition {competition!r}; known: {sorted(COMPETITIONS)}")
        data = _fetch_json(
            COMPETITIONS[competition], season, self.cache_dir,
            api_key=self._api_key, client=self._client, refresh=refresh,
            retries=3, sleep=time.sleep,
        )
        return _parse(data, competition, season)

    def fetch_odds(self, competition: str, season: str) -> pd.DataFrame:
        """football-data.org has no odds — always empty (CL/WC are shadow-mode)."""
        return pd.DataFrame({c: pd.Series(dtype="object") for c in schema.ODDS_COLUMNS})
