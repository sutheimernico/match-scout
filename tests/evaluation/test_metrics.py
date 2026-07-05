import numpy as np
import pytest

from matchscout.evaluation.metrics import brier_score, log_loss, reliability_curve


def test_brier_perfect_is_zero():
    probs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    assert brier_score(probs, [0, 1]) == pytest.approx(0.0)


def test_brier_worst_binary():
    # predict class 0 with certainty, truth is class 1 -> (1-0)^2 + (0-1)^2 = 2
    assert brier_score(np.array([[1.0, 0.0]]), [1]) == pytest.approx(2.0)


def test_log_loss_perfect_near_zero():
    probs = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert log_loss(probs, [0, 1]) == pytest.approx(0.0, abs=1e-10)


def test_log_loss_uniform_two_class():
    probs = np.array([[0.5, 0.5], [0.5, 0.5]])
    assert log_loss(probs, [0, 1]) == pytest.approx(np.log(2))


def test_reliability_well_calibrated():
    # 100 samples predicted 0.7, 70 positives -> that bin: pred ~0.7, obs ~0.7
    prob = np.full(100, 0.7)
    y = np.array([1] * 70 + [0] * 30)
    pred, obs, cnt = reliability_curve(prob, y, n_bins=10)
    assert len(pred) == 1
    assert pred[0] == pytest.approx(0.7)
    assert obs[0] == pytest.approx(0.7)
    assert cnt[0] == 100


def test_reliability_skips_empty_bins():
    prob = np.array([0.05, 0.95])
    y = np.array([0, 1])
    pred, obs, cnt = reliability_curve(prob, y, n_bins=10)
    assert len(pred) == 2  # only the two occupied bins returned
    assert cnt.sum() == 2


def test_better_calibration_scores_lower():
    y = np.array([0, 1, 0, 1])
    good = np.array([[0.9, 0.1], [0.1, 0.9], [0.8, 0.2], [0.2, 0.8]])
    bad = np.array([[0.4, 0.6], [0.6, 0.4], [0.5, 0.5], [0.5, 0.5]])
    assert brier_score(good, y) < brier_score(bad, y)
    assert log_loss(good, y) < log_loss(bad, y)
