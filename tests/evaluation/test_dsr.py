"""The trials-adjusted (Deflated Sharpe) hurdle — pinned against hand-computed references.

Reference series (deterministic, no RNG): 400 unit bets, `wins` of +1 and the rest -1, so the
per-bet Sharpe is exactly mean/sd and every intermediate quantity is reproducible by hand.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from matchscout.evaluation.dsr import (
    deflated_sharpe,
    expected_max_sharpe,
    hurdle_verdict,
    sharpe_ratio,
)


def series(wins: int, losses: int) -> np.ndarray:
    return np.array([1.0] * wins + [-1.0] * losses)


def test_sharpe_ratio_of_a_coin_flip_book():
    # 210 wins / 190 losses on unit bets: mean = 0.05, sd = 1.0 (ddof=1) -> SR = 0.05
    assert sharpe_ratio(series(210, 190)) == pytest.approx(0.05, abs=1e-9)


def test_sharpe_ratio_needs_variance_and_length():
    assert math.isnan(sharpe_ratio([1.0]))
    assert math.isnan(sharpe_ratio([1.0, 1.0, 1.0]))


def test_expected_max_sharpe_hand_reference():
    # sr_std * [(1-g) * Z^-1(1 - 1/N) + g * Z^-1(1 - 1/(N*e))], g = 0.5772156649
    # N=2:  0.2 * [(0.4227860) * 0.0000000 + 0.5772157 * 0.9006...] = 0.1039510689
    # N=10: 0.2 * [(0.4227860) * 1.2815516 + 0.5772157 * 1.7907...] = 0.3149196603
    assert expected_max_sharpe(2, 0.2) == pytest.approx(0.10395106885611878, rel=1e-12)
    assert expected_max_sharpe(10, 0.2) == pytest.approx(0.31491966026915, rel=1e-12)


def test_a_single_trial_carries_no_selection_bias():
    assert expected_max_sharpe(1, 0.2) == 0.0
    assert expected_max_sharpe(0, 0.2) == 0.0


def test_more_trials_raise_the_bar_monotonically():
    bars = [expected_max_sharpe(n, 0.2) for n in (2, 5, 20, 100, 1000)]
    assert bars == sorted(bars)


def test_deflated_sharpe_hand_reference_single_trial():
    out = deflated_sharpe(series(210, 190), n_trials=1)
    assert out["n_bets"] == 400
    assert out["sharpe"] == pytest.approx(0.05, abs=1e-9)
    assert out["expected_max_sharpe"] == 0.0
    assert out["dsr"] == pytest.approx(0.8404354583220579, rel=1e-9)
    assert out["hurdle_met"] is False
    assert out["sr_std_source"] == "null-sampling-fallback"


def test_the_same_result_fails_harder_once_twenty_configs_were_tried():
    one = deflated_sharpe(series(210, 190), n_trials=1)
    twenty = deflated_sharpe(series(210, 190), n_trials=20)
    assert twenty["expected_max_sharpe"] == pytest.approx(0.0951544150102792, rel=1e-9)
    assert twenty["dsr"] == pytest.approx(0.18413969829837162, rel=1e-9)
    assert twenty["dsr"] < one["dsr"]  # identical data, more search -> less credible


def test_a_strong_result_clears_the_bar_until_the_search_gets_big():
    strong = series(250, 150)  # SR 0.2579 per bet — implausibly good for a betting book
    assert deflated_sharpe(strong, n_trials=1)["hurdle_met"] is True
    assert deflated_sharpe(strong, n_trials=20)["hurdle_met"] is True
    assert deflated_sharpe(strong, n_trials=10_000)["hurdle_met"] is False


def test_observed_trial_spread_is_used_when_given():
    out = deflated_sharpe(series(210, 190), n_trials=20, sr_std=0.2)
    assert out["sr_std_source"] == "observed-across-trials"
    assert out["expected_max_sharpe"] == pytest.approx(expected_max_sharpe(20, 0.2), rel=1e-12)


def test_too_few_bets_yields_no_verdict():
    out = deflated_sharpe([1.0, -1.0], n_trials=5)
    assert math.isnan(out["dsr"])
    assert out["hurdle_met"] is False
    assert "Too few settled bets" in hurdle_verdict(out)


def test_verdict_text_states_the_bar_and_the_trial_count():
    text = hurdle_verdict(deflated_sharpe(series(210, 190), n_trials=7))
    assert "7 logged trials" in text
    assert "Hurdle NOT met" in text
    assert "MET" in hurdle_verdict(deflated_sharpe(series(250, 150), n_trials=1))
