import httpx
import pandas as pd
import pytest

from matchscout.data import football_data_co_uk as fd

_FLAT_CSV = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,PSH,PSD,PSA,"
    "AvgH,AvgD,AvgA,PSCH,PSCD,PSCA\n"
    "E0,12/08/2023,15:00,Alpha,Bravo,2,1,H,1.80,3.60,4.50,1.82,3.70,4.60,1.78,3.55,4.40,"
    "1.77,3.80,4.90\n"
)


def _mock_client(body: bytes, fail_times: int = 0):
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= fail_times:
            return httpx.Response(503)
        return httpx.Response(200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def _flat_raw() -> pd.DataFrame:
    """3 matches in the 2019/20+ flat schema: two played, one scheduled.

    Synthetic data (real column names, fabricated values) — the raw CSVs are not
    redistributable. Match 2 has a missing B365 draw price to exercise per-row drop.
    """
    return pd.DataFrame(
        {
            "Div": ["E0", "E0", "E0"],
            "Date": ["12/08/2023", "13/08/2023", "20/08/2023"],
            "Time": ["15:00", "17:30", "14:00"],
            "HomeTeam": ["Alpha", "Charlie", "Echo"],
            "AwayTeam": ["Bravo", "Delta", "Foxtrot"],
            "FTHG": [2, 0, ""],
            "FTAG": [1, 0, ""],
            "FTR": ["H", "D", ""],
            "B365H": [1.80, 2.50, ""], "B365D": [3.60, "", ""], "B365A": [4.50, 2.80, ""],
            "PSH": [1.82, 2.55, ""], "PSD": [3.70, 3.40, ""], "PSA": [4.60, 2.85, ""],
            "AvgH": [1.78, 2.48, ""], "AvgD": [3.55, 3.35, ""], "AvgA": [4.40, 2.78, ""],
            "B365>2.5": [1.90, 2.10, ""], "B365<2.5": [1.90, 1.72, ""],
            "P>2.5": [1.95, 2.15, ""], "P<2.5": [1.92, 1.75, ""],
            "Avg>2.5": [1.88, 2.05, ""], "Avg<2.5": [1.91, 1.74, ""],
            "B365CH": [1.75, 2.45, ""], "B365CD": [3.75, 3.50, ""], "B365CA": [4.80, 2.90, ""],
            "PSCH": [1.77, 2.50, ""], "PSCD": [3.80, 3.55, ""], "PSCA": [4.90, 2.95, ""],
            "AvgCH": [1.74, 2.43, ""], "AvgCD": [3.70, 3.45, ""], "AvgCA": [4.70, 2.88, ""],
            "B365C>2.5": [1.85, 2.05, ""], "B365C<2.5": [1.95, 1.78, ""],
            "PC>2.5": [1.90, 2.10, ""], "PC<2.5": [1.98, 1.80, ""],
            "AvgC>2.5": [1.86, 2.02, ""], "AvgC<2.5": [1.94, 1.77, ""],
        }
    )


def _bb_raw() -> pd.DataFrame:
    """2 played matches in the <=2018/19 Bb schema: no Time, 2-digit year, PSC closing."""
    return pd.DataFrame(
        {
            "Div": ["E0", "E0"],
            "Date": ["13/08/16", "13/08/16"],
            "HomeTeam": ["Alpha", "Charlie"],
            "AwayTeam": ["Bravo", "Delta"],
            "FTHG": [1, 2], "FTAG": [0, 2], "FTR": ["H", "D"],
            "B365H": [2.40, 2.00], "B365D": [3.30, 3.30], "B365A": [3.25, 4.50],
            "PSH": [2.47, 2.06], "PSD": [3.32, 3.29], "PSA": [3.19, 4.32],
            "BbAvH": [2.43, 2.01], "BbAvD": [3.21, 3.23], "BbAvA": [3.10, 4.16],
            "BbAv>2.5": [2.30, 2.50], "BbAv<2.5": [1.61, 1.52],
            "PSCH": [2.79, 2.25], "PSCD": [3.16, 3.15], "PSCA": [2.89, 3.86],
        }
    )


def test_flat_matches_parsed():
    matches, _ = fd.parse(_flat_raw(), "E0", "2324")
    assert len(matches) == 3
    assert list(matches["status"]) == ["played", "played", "scheduled"]
    assert matches.loc[0, "ft_home_goals"] == 2
    assert matches.loc[0, "ft_away_goals"] == 1
    assert pd.isna(matches.loc[2, "ft_home_goals"])
    assert (matches["competition"] == "E0").all()
    assert (matches["season"] == "2324").all()
    # Time column present → timestamp_event carries the kickoff hour
    assert matches.loc[0, "timestamp_event"].hour == 15
    # timestamp_known left unset (D7 imputation task); kickoff_utc unset (local time)
    assert matches["timestamp_known"].isna().all()
    assert matches["kickoff_utc"].isna().all()


def test_flat_odds_parsed():
    _, odds = fd.parse(_flat_raw(), "E0", "2324")
    assert set(odds["book"]) == {"B365", "PS", "Avg"}
    assert set(odds["market"]) == {"1x2", "ou25"}
    assert set(odds["is_closing"]) == {True, False}
    # scheduled match (Echo) has no odds
    assert not (odds["match_id"].str.contains("Echo")).any()
    # a known Pinnacle closing home price survives
    psc_home = odds[
        (odds["book"] == "PS") & (odds["is_closing"]) & (odds["selection"] == "H")
    ]
    assert (psc_home["odds"] == 1.77).any()
    # match 2 dropped exactly its missing B365 pre-match draw row
    assert len(odds) == 59


def test_flat_missing_odds_dropped():
    _, odds = fd.parse(_flat_raw(), "E0", "2324")
    charlie = odds[odds["match_id"].str.contains("Charlie")]
    b365_pre_draw = charlie[
        (charlie["book"] == "B365")
        & (~charlie["is_closing"])
        & (charlie["market"] == "1x2")
        & (charlie["selection"] == "D")
    ]
    assert b365_pre_draw.empty


def test_bb_era_no_time_two_digit_year():
    matches, odds = fd.parse(_bb_raw(), "E0", "1617")
    assert len(matches) == 2
    assert matches.loc[0, "timestamp_event"] == pd.Timestamp("2016-08-13")
    # Bb era has PSC 1X2 closing but no O/U closing and no B365 O/U
    assert set(odds["book"]) == {"B365", "PS", "Avg"}
    assert set(odds["market"]) == {"1x2", "ou25"}
    ou_closing = odds[(odds["market"] == "ou25") & (odds["is_closing"])]
    assert ou_closing.empty
    assert (odds["is_closing"] & (odds["market"] == "1x2")).any()  # PSC present
    assert len(odds) == 28


def test_match_id_shared_between_matches_and_odds():
    matches, odds = fd.parse(_flat_raw(), "E0", "2324")
    played_ids = set(matches[matches["status"] == "played"]["match_id"])
    assert set(odds["match_id"]).issubset(played_ids)


def test_season_url():
    assert fd.season_url("2324", "E0") == "https://www.football-data.co.uk/mmz4281/2324/E0.csv"


def test_fetch_writes_cache_and_parses(tmp_path):
    client, _calls = _mock_client(_FLAT_CSV.encode())
    prov = fd.FootballDataCoUk(tmp_path, client=client)
    matches = prov.fetch_matches("E0", "2324")
    assert len(matches) == 1
    assert (tmp_path / "football_data_co_uk" / "2324" / "E0.csv").exists()


def test_cache_read_needs_no_network(tmp_path):
    path = tmp_path / "football_data_co_uk" / "2324" / "E0.csv"
    path.parent.mkdir(parents=True)
    path.write_text(_FLAT_CSV)
    prov = fd.FootballDataCoUk(tmp_path)  # no client → would fail if it hit the network
    odds = prov.fetch_odds("E0", "2324")
    assert not odds.empty
    assert set(odds["book"]) == {"B365", "PS", "Avg"}


def test_retry_then_success(tmp_path):
    client, calls = _mock_client(_FLAT_CSV.encode(), fail_times=2)
    df = fd.fetch_raw("2324", "E0", tmp_path, client=client, sleep=lambda _: None)
    assert calls["n"] == 3
    assert len(df) == 1


def test_retry_exhausted_raises(tmp_path):
    client, _calls = _mock_client(_FLAT_CSV.encode(), fail_times=99)
    with pytest.raises(RuntimeError, match="failed to fetch"):
        fd.fetch_raw("2324", "E0", tmp_path, client=client, retries=2, sleep=lambda _: None)


def test_unknown_competition_raises(tmp_path):
    prov = fd.FootballDataCoUk(tmp_path)
    with pytest.raises(KeyError, match="unknown competition"):
        prov.fetch_matches("XX", "2324")
