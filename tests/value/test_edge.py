import pandas as pd
import pytest

from matchscout.value.edge import edge, select_value_bets


def test_edge_math():
    assert edge(0.5, 3.0) == pytest.approx(0.5)  # +EV
    assert edge(0.4, 2.0) == pytest.approx(-0.2)  # -EV
    assert edge(1 / 3, 3.0) == pytest.approx(0.0)  # fair


def _preds():
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "p_H": [0.55, 0.30],
            "p_D": [0.25, 0.30],
            "p_A": [0.20, 0.40],
            "p_over": [0.60, 0.45],
            "p_under": [0.40, 0.55],
        }
    )


def _odds(rows):
    return pd.DataFrame(
        rows,
        columns=["match_id", "market", "selection", "book", "odds", "is_closing"],
    )


def test_selects_only_positive_edge():
    # m1 home: p=0.55, odds 2.0 -> edge 0.10 (+). m2 away: p=0.40 odds 2.0 -> edge -0.20 (-).
    odds = _odds(
        [
            ("m1", "1x2", "H", "B365", 2.00, False),
            ("m2", "1x2", "A", "B365", 2.00, False),
        ]
    )
    picks = select_value_bets(_preds(), odds, threshold=0.0)
    assert list(picks["match_id"]) == ["m1"]
    assert picks.iloc[0]["edge"] == pytest.approx(0.10)


def test_threshold_filters():
    odds = _odds([("m1", "1x2", "H", "B365", 2.00, False)])  # edge 0.10
    assert len(select_value_bets(_preds(), odds, threshold=0.05)) == 1
    assert len(select_value_bets(_preds(), odds, threshold=0.20)) == 0


def test_ignores_closing_odds():
    odds = _odds(
        [
            ("m1", "1x2", "H", "B365", 2.00, True),  # closing -> ignored for placement
        ]
    )
    assert select_value_bets(_preds(), odds).empty


def test_ignores_other_books():
    odds = _odds([("m1", "1x2", "H", "PS", 2.00, False)])
    assert select_value_bets(_preds(), odds, book="B365").empty


def test_sorted_by_edge_descending():
    odds = _odds(
        [
            ("m1", "1x2", "H", "B365", 2.00, False),  # edge 0.10
            ("m1", "ou25", "over", "B365", 2.00, False),  # p 0.60 -> edge 0.20
        ]
    )
    picks = select_value_bets(_preds(), odds)
    assert list(picks["edge"]) == sorted(picks["edge"], reverse=True)
    assert picks.iloc[0]["selection"] == "over"
