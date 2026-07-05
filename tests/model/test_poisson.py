import math

import numpy as np
import pytest

from matchscout.model import poisson


def test_score_matrix_normalized():
    m = poisson.score_matrix(1.5, 1.2)
    assert m.sum() == pytest.approx(1.0)


def test_zero_zero_probability_matches_poisson():
    # After renormalization P(0-0) ~ exp(-(lh+ma)) / total_mass; with max_goals=10 the
    # truncated mass is negligible, so it should be very close to the analytic value.
    lh, ma = 1.4, 1.1
    m = poisson.score_matrix(lh, ma)
    assert m[0, 0] == pytest.approx(math.exp(-(lh + ma)), rel=1e-3)


def test_markets_sum_to_one():
    probs = poisson.market_probs(poisson.score_matrix(1.7, 1.3))
    assert sum(probs["1x2"].values()) == pytest.approx(1.0)
    assert sum(probs["ou25"].values()) == pytest.approx(1.0)


def test_symmetry_equal_rates():
    probs = poisson.market_probs(poisson.score_matrix(1.5, 1.5))
    assert probs["1x2"]["H"] == pytest.approx(probs["1x2"]["A"])


def test_stronger_home_raises_home_win():
    weak = poisson.market_probs(poisson.score_matrix(1.2, 1.2))["1x2"]["H"]
    strong = poisson.market_probs(poisson.score_matrix(2.4, 1.2))["1x2"]["H"]
    assert strong > weak


def test_more_goals_raises_over():
    low = poisson.market_probs(poisson.score_matrix(0.8, 0.7))["ou25"]["over"]
    high = poisson.market_probs(poisson.score_matrix(2.2, 1.9))["ou25"]["over"]
    assert high > low


def test_nonpositive_rate_raises():
    with pytest.raises(ValueError, match="positive"):
        poisson.score_matrix(0.0, 1.0)


def test_over_under_partition():
    # over (>=3 goals) and under (<=2 goals) must partition the whole matrix
    m = poisson.score_matrix(1.6, 1.4)
    probs = poisson.market_probs(m)
    assert probs["ou25"]["over"] + probs["ou25"]["under"] == pytest.approx(float(m.sum()))


def test_known_value_1_1_draw():
    # lambda=mu=1: independent Poisson, P(draw) = sum_k P(k)^2 with P(k)=e^-1/k!
    m = poisson.score_matrix(1.0, 1.0, max_goals=20)
    probs = poisson.market_probs(m)
    expected_draw = sum((math.exp(-1.0) / math.factorial(k)) ** 2 for k in range(21))
    assert probs["1x2"]["D"] == pytest.approx(expected_draw, rel=1e-4)


def test_matrix_is_square():
    m = poisson.score_matrix(1.0, 1.0)
    assert m.shape == (poisson.MAX_GOALS + 1, poisson.MAX_GOALS + 1)
    assert isinstance(m, np.ndarray)
