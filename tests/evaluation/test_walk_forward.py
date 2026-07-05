import pandas as pd
import pytest

from matchscout.evaluation.walk_forward import walk_forward_predict

_SCORES = {
    ("A", "B"): (2, 0), ("A", "C"): (1, 0), ("A", "D"): (3, 1),
    ("B", "A"): (1, 1), ("B", "C"): (2, 1), ("B", "D"): (2, 0),
    ("C", "A"): (0, 2), ("C", "B"): (1, 1), ("C", "D"): (1, 0),
    ("D", "A"): (0, 1), ("D", "B"): (0, 2), ("D", "C"): (1, 1),
}


def _season(rounds: int = 2, extra: list | None = None) -> pd.DataFrame:
    rows = []
    day = pd.Timestamp("2023-08-01")
    for _ in range(rounds):
        for (h, a), (hg, ag) in _SCORES.items():
            rows.append((h, a, hg, ag, day))
            day += pd.Timedelta(days=3)
    if extra:
        for (h, a, hg, ag) in extra:
            rows.append((h, a, hg, ag, day))
            day += pd.Timedelta(days=3)
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(len(rows))],
            "competition": ["E0"] * len(rows),
            "status": ["played"] * len(rows),
            "date": [r[4] for r in rows],
            "home": [r[0] for r in rows],
            "away": [r[1] for r in rows],
            "ft_home_goals": [r[2] for r in rows],
            "ft_away_goals": [r[3] for r in rows],
        }
    )


def test_output_structure():
    preds = walk_forward_predict(_season(), min_train=6, half_life_days=None)
    assert not preds.empty
    for col in ["match_id", "p_H", "p_D", "p_A", "p_over", "p_under", "outcome_1x2"]:
        assert col in preds.columns
    row = preds.iloc[0]
    assert row["p_H"] + row["p_D"] + row["p_A"] == pytest.approx(1.0)
    assert set(preds["outcome_1x2"]).issubset({"H", "D", "A"})


def test_burn_in_respected():
    preds = walk_forward_predict(_season(), min_train=6, half_life_days=None)
    assert (preds["n_train"] >= 6).all()


def test_no_lookahead():
    full = _season()
    mid = full["date"].sort_values().iloc[len(full) // 2]
    preds_full = walk_forward_predict(full, min_train=6, half_life_days=None)
    truncated = full[full["date"] <= mid]
    preds_trunc = walk_forward_predict(truncated, min_train=6, half_life_days=None)
    merged = preds_full.merge(preds_trunc, on="match_id", suffixes=("_f", "_t"))
    assert len(merged) > 0
    # predictions for past days are identical whether or not future matches exist
    assert merged["p_H_f"].to_numpy() == pytest.approx(merged["p_H_t"].to_numpy())


def test_unseen_team_skipped():
    # team "E" appears only in one late match with no prior history -> not predictable
    preds = walk_forward_predict(
        _season(extra=[("E", "A", 0, 2)]), min_train=6, half_life_days=None
    )
    last = preds[(preds["home"] == "E") | (preds["away"] == "E")]
    assert last.empty
