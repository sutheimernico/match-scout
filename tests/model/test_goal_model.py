import pandas as pd
import pytest

from matchscout.model.goal_model import GoalModel, fit_poisson

# A strong (scores lots, concedes ~none) ... D weak. Home/away balanced, repeated for signal.
_RESULTS = [
    ("A", "B", 3, 0), ("A", "C", 2, 0), ("A", "D", 4, 0),
    ("B", "A", 0, 2), ("B", "C", 2, 1), ("B", "D", 3, 0),
    ("C", "A", 0, 3), ("C", "B", 1, 1), ("C", "D", 2, 0),
    ("D", "A", 0, 4), ("D", "B", 0, 3), ("D", "C", 0, 2),
    ("A", "B", 2, 0), ("A", "C", 3, 1), ("A", "D", 3, 0),
    ("D", "A", 1, 3), ("D", "B", 0, 2), ("D", "C", 1, 2),
]


def _matches(results) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "status": ["played"] * len(results),
            "home": [r[0] for r in results],
            "away": [r[1] for r in results],
            "ft_home_goals": [r[2] for r in results],
            "ft_away_goals": [r[3] for r in results],
        }
    )


def test_fit_recovers_strength_ordering():
    m = fit_poisson(_matches(_RESULTS))
    assert m.attack["A"] > m.attack["D"]
    assert m.defence["A"] > m.defence["D"]  # A concedes fewest -> highest defensive strength


def test_home_advantage_positive():
    m = fit_poisson(_matches(_RESULTS))
    assert m.home_adv > 0


def test_predict_reflects_strength():
    m = fit_poisson(_matches(_RESULTS))
    strong_home = m.predict("A", "D")["1x2"]["H"]
    weak_home = m.predict("D", "A")["1x2"]["H"]
    assert strong_home > weak_home
    probs = m.predict("A", "D")
    assert sum(probs["1x2"].values()) == pytest.approx(1.0)


def test_rates_positive():
    m = fit_poisson(_matches(_RESULTS))
    lam, mu = m.rates("A", "D")
    assert lam > 0 and mu > 0
    assert lam > mu  # strong home vs weak away


def test_deterministic():
    a = fit_poisson(_matches(_RESULTS))
    b = fit_poisson(_matches(_RESULTS))
    assert a.attack == b.attack
    assert a.defence == b.defence


def test_unknown_team_raises():
    m = fit_poisson(_matches(_RESULTS))
    with pytest.raises(KeyError, match="unknown team"):
        m.rates("A", "ZZ")


def test_no_played_matches_raises():
    empty = pd.DataFrame(
        {"status": ["scheduled"], "home": ["A"], "away": ["B"],
         "ft_home_goals": [pd.NA], "ft_away_goals": [pd.NA]}
    )
    with pytest.raises(ValueError, match="no played matches"):
        fit_poisson(empty)


def test_isinstance_goalmodel():
    assert isinstance(fit_poisson(_matches(_RESULTS)), GoalModel)
