import httpx
import pandas as pd
import pytest

from matchscout.data.football_data_org import FootballDataOrg
from matchscout.data.provider import MatchProvider

_JSON = {
    "matches": [
        {
            "id": 1, "utcDate": "2024-06-01T19:00:00Z", "status": "FINISHED",
            "homeTeam": {"name": "Real Madrid"}, "awayTeam": {"name": "Dortmund"},
            "score": {"fullTime": {"home": 2, "away": 0}},
        },
        {
            "id": 2, "utcDate": "2026-07-10T19:00:00Z", "status": "SCHEDULED",
            "homeTeam": {"name": "Team A"}, "awayTeam": {"name": "Team B"},
            "score": {"fullTime": {"home": None, "away": None}},
        },
    ]
}


def _mock_client(payload):
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_conforms_to_match_provider():
    assert isinstance(FootballDataOrg("cache", api_key="x"), MatchProvider)


def test_fetch_parses_and_caches(tmp_path):
    prov = FootballDataOrg(tmp_path, api_key="test", client=_mock_client(_JSON))
    matches = prov.fetch_matches("CL", "2023")
    assert list(matches["status"]) == ["played", "scheduled"]
    assert matches.loc[0, "ft_home_goals"] == 2
    assert pd.isna(matches.loc[1, "ft_home_goals"])
    assert matches.loc[0, "kickoff_utc"] is not pd.NaT  # real UTC populated
    assert (tmp_path / "football_data_org" / "CL_2023.json").exists()


def test_cache_read_needs_no_key(tmp_path):
    # pre-seed cache, then a provider with NO key must still read it
    prov = FootballDataOrg(tmp_path, api_key="test", client=_mock_client(_JSON))
    prov.fetch_matches("CL", "2023")
    prov2 = FootballDataOrg(tmp_path, api_key=None)
    assert len(prov2.fetch_matches("CL", "2023")) == 2


def test_no_key_no_cache_raises(tmp_path):
    prov = FootballDataOrg(tmp_path, api_key=None)
    with pytest.raises(RuntimeError, match="FOOTBALL_DATA_API_KEY"):
        prov.fetch_matches("WC", "2026")


def test_unknown_competition_raises(tmp_path):
    prov = FootballDataOrg(tmp_path, api_key="x")
    with pytest.raises(KeyError, match="unknown competition"):
        prov.fetch_matches("XX", "2023")


def test_fetch_odds_always_empty(tmp_path):
    prov = FootballDataOrg(tmp_path, api_key="x")
    assert prov.fetch_odds("CL", "2023").empty
