import pandas as pd
import pytest

from matchscout.model.goal_model import (
    GoalModel,
    LookaheadError,
    _apply_tau,
    fit_dixon_coles,
    fit_poisson,
)
from matchscout.model.poisson import score_matrix

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
            "date": pd.date_range("2024-01-06", periods=len(results), freq="7D"),
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


def test_dixon_coles_rho_in_bounds():
    m = fit_dixon_coles(_matches(_RESULTS), as_of=pd.Timestamp("2030-01-01"))
    assert -0.2 <= m.rho <= 0.2
    assert sum(m.predict("A", "D")["1x2"].values()) == pytest.approx(1.0)


def test_apply_tau_renormalizes_and_shifts_low_scores():
    m = score_matrix(1.4, 1.2)
    corrected = _apply_tau(m, 1.4, 1.2, -0.1)
    assert corrected.sum() == pytest.approx(1.0)
    assert corrected[0, 0] != pytest.approx(m[0, 0])


def test_time_decay_upweights_recent_form():
    rows = []
    for _ in range(3):  # old: X weak
        rows.append(("X", "Y", 0, 3, "2023-01-15"))
        rows.append(("Y", "X", 3, 0, "2023-01-20"))
    for _ in range(3):  # recent: X strong
        rows.append(("X", "Y", 3, 0, "2023-12-15"))
        rows.append(("Y", "X", 0, 3, "2023-12-20"))
    df = pd.DataFrame(
        {
            "status": ["played"] * len(rows),
            "home": [r[0] for r in rows],
            "away": [r[1] for r in rows],
            "ft_home_goals": [r[2] for r in rows],
            "ft_away_goals": [r[3] for r in rows],
            "date": pd.to_datetime([r[4] for r in rows]),
        }
    )
    as_of = pd.Timestamp("2023-12-31")
    recent = fit_dixon_coles(df, half_life_days=20, as_of=as_of)
    flat = fit_dixon_coles(df, half_life_days=1e6, as_of=as_of)
    assert recent.attack["X"] > flat.attack["X"]


def _dated(rows, dates):
    return pd.DataFrame(
        {
            "status": ["played"] * len(rows),
            "home": [r[0] for r in rows],
            "away": [r[1] for r in rows],
            "ft_home_goals": [r[2] for r in rows],
            "ft_away_goals": [r[3] for r in rows],
            "date": pd.to_datetime(dates),
        }
    )


_POISONED = [("A", "B", 2, 0), ("B", "A", 1, 1), ("A", "B", 3, 1), ("B", "A", 0, 2)]


def test_fit_rejects_a_training_row_from_the_prediction_day():
    df = _dated(_POISONED, ["2024-01-01", "2024-01-08", "2024-01-15", "2024-02-01"])
    with pytest.raises(LookaheadError, match="on or after as_of"):
        fit_dixon_coles(df, as_of=pd.Timestamp("2024-02-01"))


def test_fit_rejects_a_training_row_from_the_future():
    df = _dated(_POISONED, ["2024-01-01", "2024-01-08", "2024-01-15", "2024-03-01"])
    with pytest.raises(LookaheadError, match="1 training match"):
        fit_dixon_coles(df, as_of=pd.Timestamp("2024-02-01"))


def test_fit_accepts_history_strictly_before_as_of():
    df = _dated(_POISONED, ["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"])
    assert isinstance(fit_dixon_coles(df, as_of=pd.Timestamp("2024-02-01")), GoalModel)


def test_guard_works_across_the_tz_aware_naive_seam():
    # football-data.co.uk is tz-naive, football-data.org is tz-aware UTC: neither combination
    # may crash the guard, and neither may let a future row through.
    naive = _dated(_POISONED, ["2024-01-01", "2024-01-08", "2024-01-15", "2024-03-01"])
    with pytest.raises(LookaheadError):
        fit_dixon_coles(naive, as_of=pd.Timestamp("2024-02-01", tz="UTC"))

    aware = _dated(
        _POISONED,
        pd.to_datetime(
            ["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"], utc=True
        ),
    )
    assert isinstance(fit_dixon_coles(aware, as_of=pd.Timestamp("2024-02-01")), GoalModel)


def test_poisson_ablation_enforces_as_of_when_given():
    df = _dated(_POISONED, ["2024-01-01", "2024-01-08", "2024-01-15", "2024-03-01"])
    assert isinstance(fit_poisson(df), GoalModel)  # ablation, no boundary claimed
    with pytest.raises(LookaheadError):
        fit_poisson(df, as_of=pd.Timestamp("2024-02-01"))
