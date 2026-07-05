import pandas as pd
import pytest

from matchscout.evaluation.calibration import calibration_report, market_probs_1x2


def _odds(match_ids, prices=(2.0, 3.5, 3.6)):
    rows = []
    for mid in match_ids:
        for sel, price in zip(["H", "D", "A"], prices, strict=True):
            rows.append(
                {
                    "match_id": mid,
                    "market": "1x2",
                    "selection": sel,
                    "book": "PS",
                    "odds": price,
                    "is_closing": True,
                    "collected_at": pd.NaT,
                }
            )
    return pd.DataFrame(rows)


def _preds(match_ids, probs, outcomes):
    return pd.DataFrame(
        {
            "match_id": match_ids,
            "p_H": [p[0] for p in probs],
            "p_D": [p[1] for p in probs],
            "p_A": [p[2] for p in probs],
            "outcome_1x2": outcomes,
        }
    )


def test_market_probs_devigged_sum_to_one():
    m = market_probs_1x2(_odds(["m1"]))
    assert m["m1"].sum() == pytest.approx(1.0)


def test_report_flags_market_better_when_model_is_bad():
    ids = ["m1", "m2", "m3", "m4"]
    outcomes = ["H", "D", "A", "H"]
    bad = [[0.34, 0.33, 0.33]] * 4  # uninformative model
    report = calibration_report(_preds(ids, bad, outcomes), _odds(ids))
    assert report["n"] == 4
    assert report["beats_closing_line"] is False
    assert "does NOT beat" in report["verdict"]


def test_report_flags_model_better_when_model_is_perfect():
    ids = ["m1", "m2", "m3", "m4"]
    outcomes = ["H", "D", "A", "H"]
    onehot = {"H": [1.0, 0.0, 0.0], "D": [0.0, 1.0, 0.0], "A": [0.0, 0.0, 1.0]}
    perfect = [onehot[o] for o in outcomes]
    report = calibration_report(_preds(ids, perfect, outcomes), _odds(ids))
    assert report["beats_closing_line"] is True
    assert report["model"]["brier"] < report["market"]["brier"]


def test_no_overlap_raises():
    preds = _preds(["x1"], [[0.4, 0.3, 0.3]], ["H"])
    with pytest.raises(ValueError, match="no matches"):
        calibration_report(preds, _odds(["m1"]))
