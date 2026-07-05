import pandas as pd
import pytest

from matchscout.ml.dataset import FEATURE_COLUMNS, build_1x2_dataset


def _preds(ids, outcomes):
    return pd.DataFrame(
        {
            "match_id": ids,
            "p_H": [0.5] * len(ids),
            "p_D": [0.3] * len(ids),
            "p_A": [0.2] * len(ids),
            "p_over": [0.55] * len(ids),
            "p_under": [0.45] * len(ids),
            "outcome_1x2": outcomes,
        }
    )


def _closing_odds(ids):
    rows = []
    for mid in ids:
        for sel, price in zip(["H", "D", "A"], [2.0, 3.5, 3.6], strict=True):
            rows.append((mid, "1x2", sel, "PS", price, True))
    return pd.DataFrame(
        rows, columns=["match_id", "market", "selection", "book", "odds", "is_closing"]
    )


def test_dataset_shape_and_columns():
    ids = ["m1", "m2", "m3"]
    X, y, mids = build_1x2_dataset(_preds(ids, ["H", "D", "A"]), _closing_odds(ids))
    assert list(X.columns) == FEATURE_COLUMNS
    assert len(X) == 3 == len(y) == len(mids)
    assert list(y) == [0, 1, 2]


def test_market_features_devigged_sum_to_one():
    ids = ["m1"]
    X, _, _ = build_1x2_dataset(_preds(ids, ["H"]), _closing_odds(ids))
    assert X.loc[0, ["mkt_H", "mkt_D", "mkt_A"]].sum() == pytest.approx(1.0)


def test_only_matches_with_market_kept():
    # m2 has no closing odds -> dropped
    X, y, mids = build_1x2_dataset(_preds(["m1", "m2"], ["H", "A"]), _closing_odds(["m1"]))
    assert list(mids) == ["m1"]


def test_no_overlap_raises():
    with pytest.raises(ValueError, match="no matches"):
        build_1x2_dataset(_preds(["x1"], ["H"]), _closing_odds(["m1"]))
