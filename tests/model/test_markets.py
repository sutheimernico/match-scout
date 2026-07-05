import pytest

from matchscout.model.markets import (
    all_over_under,
    btts,
    correct_score,
    double_chance,
    over_under,
    to_advance,
)
from matchscout.model.poisson import market_probs, score_matrix


def test_over_under_partition():
    m = score_matrix(1.5, 1.3)
    over, under = over_under(m, 2.5)
    assert over + under == pytest.approx(1.0)


def test_over_under_lines_monotonic():
    m = score_matrix(1.8, 1.4)
    p = all_over_under(m)
    lines = sorted(p)
    overs = [p[line] for line in lines]
    assert overs == sorted(overs, reverse=True)  # higher line -> lower P(over)
    assert p[0.5] > p[4.5]


def test_btts():
    yes, no = btts(score_matrix(1.5, 1.5))
    assert yes + no == pytest.approx(1.0)
    high = btts(score_matrix(2.5, 2.5))[0]
    low = btts(score_matrix(0.5, 0.5))[0]
    assert high > low


def test_correct_score_sorted():
    scores = correct_score(score_matrix(1.4, 1.1), top_n=5)
    assert len(scores) == 5
    probs = [p for _, p in scores]
    assert probs == sorted(probs, reverse=True)
    assert all("-" in s for s, _ in scores)


def test_double_chance_sums_to_two():
    dc = double_chance(score_matrix(1.5, 1.2))
    assert dc["1X"] + dc["12"] + dc["X2"] == pytest.approx(2.0)


def test_to_advance_partition_and_exceeds_reg_win():
    p_home, p_away = to_advance(1.8, 1.0)
    assert p_home + p_away == pytest.approx(1.0)
    reg_home_win = market_probs(score_matrix(1.8, 1.0))["1x2"]["H"]
    # advancing includes converting some regulation draws -> strictly above the 90-min win prob
    assert p_home > reg_home_win


def test_to_advance_symmetry():
    p_home, p_away = to_advance(1.3, 1.3)
    assert p_home == pytest.approx(0.5, abs=1e-9)
