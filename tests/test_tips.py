import pandas as pd
import pytest

from matchscout.model.poisson import most_likely_score, score_matrix
from matchscout.tips import TIP_COLUMNS, fixture_tips, suggest_combo

_RESULTS = [
    ("A", "B", 3, 0), ("A", "C", 2, 0), ("A", "D", 4, 0),
    ("B", "A", 0, 2), ("B", "C", 2, 1), ("B", "D", 3, 0),
    ("C", "A", 0, 3), ("C", "B", 1, 1), ("C", "D", 2, 0),
    ("D", "A", 0, 4), ("D", "B", 0, 3), ("D", "C", 1, 2),
    ("A", "B", 2, 0), ("A", "D", 3, 0), ("D", "A", 1, 3),
]


def _train():
    day = pd.Timestamp("2024-01-01")
    rows = []
    for i, (h, a, hg, ag) in enumerate(_RESULTS):
        rows.append((f"t{i}", day + pd.Timedelta(days=3 * i), "played", h, a, hg, ag))
    return pd.DataFrame(
        rows,
        columns=["match_id", "date", "status", "home", "away", "ft_home_goals", "ft_away_goals"],
    )


def _fixtures(pairs):
    return pd.DataFrame(
        [{"match_id": f"f{i}", "date": pd.Timestamp("2024-06-01"), "home": h, "away": a}
         for i, (h, a) in enumerate(pairs)]
    )


def test_most_likely_score_home_favoured():
    assert most_likely_score(score_matrix(2.2, 0.8)) == (2, 0)


def test_tips_columns_and_pick():
    tips = fixture_tips(_train(), _fixtures([("A", "D")]), as_of=pd.Timestamp("2024-06-01"))
    assert list(tips.columns) == TIP_COLUMNS
    assert len(tips) == 1
    row = tips.iloc[0]
    assert row["tip_1x2"] == "H"  # A (strong) at home vs D (weak)
    assert row["p_H"] + row["p_D"] + row["p_A"] == pytest.approx(1.0)
    assert row["p_over05"] > row["p_over35"]  # O/U lines monotonic
    assert row["p_home_adv"] >= row["p_H"]  # advancing >= 90-min win


def test_suggest_combo():
    tips = fixture_tips(
        _train(), _fixtures([("A", "D"), ("A", "C"), ("B", "D")]),
        as_of=pd.Timestamp("2024-06-01"),
    )
    combo = suggest_combo(tips, n_legs=2)
    assert combo["n_legs"] == 2
    assert 0.0 <= combo["combined_prob"] <= 1.0
    assert len(combo["legs"]) == 2


def test_suggest_combo_empty():
    empty = fixture_tips(_train(), _fixtures([]), as_of=pd.Timestamp("2024-06-01"))
    assert suggest_combo(empty)["n_legs"] == 0


def test_unknown_team_skipped():
    tips = fixture_tips(_train(), _fixtures([("A", "Zebra")]), as_of=pd.Timestamp("2024-06-01"))
    assert tips.empty


def test_empty_fixtures_returns_typed_empty():
    tips = fixture_tips(_train(), _fixtures([]), as_of=pd.Timestamp("2024-06-01"))
    assert tips.empty
    assert list(tips.columns) == TIP_COLUMNS
