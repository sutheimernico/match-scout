import pandas as pd

from matchscout.ml.evaluate import evaluate_challenger

# closing-odds templates: the true class gets the short price, the others long.
_ODDS_BY_CLASS = {
    "H": {"H": 1.50, "D": 5.0, "A": 6.0},
    "D": {"H": 5.0, "D": 1.50, "A": 6.0},
    "A": {"H": 6.0, "D": 5.0, "A": 1.50},
}


def _synthetic(n=90):
    classes = ["H", "D", "A"]
    pred_rows, odds_rows = [], []
    for i in range(n):
        cls = classes[i % 3]
        mid = f"m{i}"
        pred_rows.append(
            {
                "match_id": mid, "p_H": 0.34, "p_D": 0.33, "p_A": 0.33,
                "p_over": 0.5, "p_under": 0.5, "outcome_1x2": cls,
            }
        )
        for sel in ("H", "D", "A"):
            odds_rows.append((mid, "1x2", sel, "PS", _ODDS_BY_CLASS[cls][sel], True))
    preds = pd.DataFrame(pred_rows)
    odds = pd.DataFrame(
        odds_rows, columns=["match_id", "market", "selection", "book", "odds", "is_closing"]
    )
    return preds, odds


def test_ml_beats_uniform_dixon_coles_on_clean_signal():
    preds, odds = _synthetic(90)
    report = evaluate_challenger(preds, odds, n_splits=3, embargo=3, n_estimators=50)
    assert report["n_oos"] > 0
    assert report["beats_dixon_coles"] is True  # market feature is informative; DC is uniform
    assert isinstance(report["verdict"], str)


def test_report_structure():
    preds, odds = _synthetic(90)
    report = evaluate_challenger(preds, odds, n_splits=3, embargo=3, n_estimators=30)
    for key in ("ml", "dixon_coles", "market"):
        assert "brier" in report[key] and "log_loss" in report[key]


def test_deterministic():
    preds, odds = _synthetic(90)
    a = evaluate_challenger(preds, odds, n_splits=3, embargo=3, n_estimators=30, seed=5)
    b = evaluate_challenger(preds, odds, n_splits=3, embargo=3, n_estimators=30, seed=5)
    assert a == b
