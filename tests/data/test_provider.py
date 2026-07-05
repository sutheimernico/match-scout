import pandas as pd

from matchscout.data import schema
from matchscout.data.fakes import FakeProvider
from matchscout.data.provider import MatchProvider, OddsProvider


def test_fake_conforms_to_protocols():
    fake = FakeProvider()
    assert isinstance(fake, MatchProvider)
    assert isinstance(fake, OddsProvider)


def test_unknown_key_returns_empty_canonical_frame():
    fake = FakeProvider()
    matches = fake.fetch_matches("E0", "2324")
    odds = fake.fetch_odds("E0", "2324")
    assert list(matches.columns) == schema.MATCH_COLUMNS
    assert list(odds.columns) == schema.ODDS_COLUMNS
    assert matches.empty
    assert odds.empty


def test_returns_copy_not_reference():
    df = pd.DataFrame({c: ["x"] for c in schema.MATCH_COLUMNS})
    fake = FakeProvider(matches={("E0", "2324"): df})
    out = fake.fetch_matches("E0", "2324")
    out.loc[0, "home"] = "MUTATED"
    assert df.loc[0, "home"] == "x"
