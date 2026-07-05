import pandas as pd

from matchscout.backtest.baselines import baseline_picks


def _matches():
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "status": ["played", "played"],
            "home": ["A", "C"],
            "away": ["B", "D"],
            "ft_home_goals": [1, 0],
            "ft_away_goals": [0, 0],
        }
    )


def _odds():
    rows = [
        ("m1", "1x2", "H", "B365", 1.50, False),
        ("m1", "1x2", "D", "B365", 4.00, False),
        ("m1", "1x2", "A", "B365", 6.00, False),
        ("m1", "ou25", "over", "B365", 1.90, False),
        ("m2", "1x2", "H", "B365", 3.00, False),
        ("m2", "1x2", "D", "B365", 3.20, False),
        ("m2", "1x2", "A", "B365", 2.40, False),
        ("m2", "ou25", "over", "B365", 2.10, False),
    ]
    return pd.DataFrame(
        rows, columns=["match_id", "market", "selection", "book", "odds", "is_closing"]
    )


def test_always_home():
    p = baseline_picks(_matches(), _odds(), "home")
    assert set(p["match_id"]) == {"m1", "m2"}
    assert (p["selection"] == "H").all()


def test_always_favorite_picks_lowest_odds():
    p = baseline_picks(_matches(), _odds(), "favorite").set_index("match_id")
    assert p.loc["m1", "selection"] == "H"  # 1.50 is shortest
    assert p.loc["m2", "selection"] == "A"  # 2.40 is shortest


def test_always_over():
    p = baseline_picks(_matches(), _odds(), "over")
    assert (p["market"] == "ou25").all()
    assert (p["selection"] == "over").all()


def test_unknown_strategy_raises():
    try:
        baseline_picks(_matches(), _odds(), "sideways")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
