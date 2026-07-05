import numpy as np
import pytest

from matchscout.value.devig import booksum, devig_proportional, devig_shin


def test_booksum_has_overround():
    # a typical 1X2 market with ~5% margin
    assert booksum([2.0, 3.5, 4.0]) > 1.0


def test_proportional_sums_to_one():
    p = devig_proportional([2.0, 3.5, 4.0])
    assert p.sum() == pytest.approx(1.0)


def test_shin_sums_to_one():
    p = devig_shin([2.0, 3.5, 4.0])
    assert p.sum() == pytest.approx(1.0)


def test_fair_market_recovered():
    # odds set exactly to 1/p (no margin) -> both methods return p
    p_true = np.array([0.5, 0.3, 0.2])
    odds = 1.0 / p_true
    assert devig_proportional(odds) == pytest.approx(p_true)
    assert devig_shin(odds) == pytest.approx(p_true, abs=1e-6)


def test_shin_differs_from_proportional_on_biased_market():
    odds = [1.30, 6.0, 15.0]  # strong favourite + longshots
    prop = devig_proportional(odds)
    shin = devig_shin(odds)
    assert not np.allclose(prop, shin)


def test_shin_corrects_favourite_longshot_bias():
    # Shin moves mass from the longshot toward the favourite vs. proportional.
    odds = [1.30, 6.0, 15.0]
    prop = devig_proportional(odds)
    shin = devig_shin(odds)
    assert shin[0] >= prop[0]  # favourite prob not lower under Shin
    assert shin[-1] <= prop[-1]  # longshot prob not higher under Shin


def test_two_way_market():
    p = devig_shin([1.9, 1.9])
    assert p.sum() == pytest.approx(1.0)
    assert p[0] == pytest.approx(0.5)
