import pandas as pd
import pytest

from matchscout.data import schema
from matchscout.data.schema import MatchStatus, SchemaError


def _matches(**overrides):
    base = {
        "match_id": ["m1"],
        "competition": ["E0"],
        "season": ["2324"],
        "date": [pd.Timestamp("2024-05-01")],
        "kickoff_utc": [pd.Timestamp("2024-05-01 14:00", tz="UTC")],
        "home": ["Arsenal"],
        "away": ["Chelsea"],
        "ft_home_goals": [2],
        "ft_away_goals": [1],
        "status": [MatchStatus.PLAYED.value],
        "timestamp_event": [pd.Timestamp("2024-05-01 14:00", tz="UTC")],
        "timestamp_known": [pd.Timestamp("2024-04-30 12:00", tz="UTC")],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def _odds(**overrides):
    base = {
        "match_id": ["m1", "m1"],
        "market": [schema.Market.ONE_X_TWO.value, schema.Market.OVER_UNDER_25.value],
        "selection": [schema.Selection.HOME.value, schema.Selection.OVER.value],
        "book": ["B365", "B365"],
        "odds": [2.1, 1.9],
        "is_closing": [False, False],
        "collected_at": [pd.Timestamp("2024-04-30 12:00", tz="UTC")] * 2,
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_valid_matches_pass():
    schema.validate_matches(_matches())


def test_valid_odds_pass():
    schema.validate_odds(_odds())


def test_missing_column_raises():
    df = _matches().drop(columns=["status"])
    with pytest.raises(SchemaError, match="missing columns"):
        schema.validate_matches(df)


def test_bad_status_raises():
    with pytest.raises(SchemaError, match="invalid status"):
        schema.validate_matches(_matches(status=["finished"]))


def test_played_without_goals_raises():
    with pytest.raises(SchemaError, match="goal columns"):
        schema.validate_matches(_matches(ft_home_goals=[pd.NA]))


def test_lookahead_timestamp_raises():
    df = _matches(timestamp_known=[pd.Timestamp("2024-05-02 00:00", tz="UTC")])
    with pytest.raises(SchemaError, match="lookahead"):
        schema.validate_matches(df)


def test_bad_market_raises():
    with pytest.raises(SchemaError, match="invalid market"):
        schema.validate_odds(_odds(market=["btts", "ou25"]))


def test_selection_wrong_for_market_raises():
    df = _odds(
        market=[schema.Market.ONE_X_TWO.value, schema.Market.ONE_X_TWO.value],
        selection=[schema.Selection.HOME.value, schema.Selection.OVER.value],
    )
    with pytest.raises(SchemaError, match="invalid for market"):
        schema.validate_odds(df)


def test_odds_not_greater_than_one_raises():
    with pytest.raises(SchemaError, match="must be > 1.0"):
        schema.validate_odds(_odds(odds=[0.9, 1.9]))


def test_empty_frames_pass():
    empty_m = pd.DataFrame({c: pd.Series(dtype="object") for c in schema.MATCH_COLUMNS})
    empty_o = pd.DataFrame({c: pd.Series(dtype="object") for c in schema.ODDS_COLUMNS})
    schema.validate_matches(empty_m)
    schema.validate_odds(empty_o)
