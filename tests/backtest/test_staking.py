import pytest

from matchscout.backtest.staking import flat_stake, kelly_full, kelly_stake


def test_flat_stake_constant():
    assert flat_stake() == 1.0
    assert flat_stake(2.5) == 2.5


def test_kelly_full_positive_edge():
    # p=0.6, odds=2.0 -> b=1, edge=0.2 -> f=0.2
    assert kelly_full(0.6, 2.0) == pytest.approx(0.2)


def test_kelly_full_no_edge_is_zero():
    assert kelly_full(0.5, 2.0) == pytest.approx(0.0)
    assert kelly_full(0.4, 2.0) == 0.0  # negative edge floored


def test_kelly_stake_quarter_of_edge():
    # 0.25 * full_kelly(0.2) = 0.05 of bankroll -> 50 on 1000, cap (0.05*1000=50) not binding
    assert kelly_stake(0.6, 2.0, 1000.0, fraction=0.25, cap=0.05) == pytest.approx(50.0)


def test_kelly_stake_cap_binds():
    # huge edge would want a large stake; cap limits to 0.05*bankroll
    stake = kelly_stake(0.95, 5.0, 1000.0, fraction=0.25, cap=0.05)
    assert stake == pytest.approx(50.0)


def test_kelly_stake_edge_shrink_reduces():
    full = kelly_stake(0.6, 2.0, 1000.0, edge_shrink=1.0)
    shrunk = kelly_stake(0.6, 2.0, 1000.0, edge_shrink=0.5)
    assert shrunk < full


def test_kelly_stake_negative_edge_zero():
    assert kelly_stake(0.4, 2.0, 1000.0) == 0.0
