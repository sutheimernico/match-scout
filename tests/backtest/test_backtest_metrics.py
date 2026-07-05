import numpy as np
import pandas as pd

from matchscout.backtest.metrics import bootstrap_ci, max_drawdown, summary, verdict


def _ledger(pnls, stakes, clvs, bankroll_start=1000.0):
    bankroll, after = bankroll_start, []
    for p in pnls:
        bankroll += p
        after.append(bankroll)
    return pd.DataFrame(
        {
            "pnl": pnls,
            "stake": stakes,
            "clv": clvs,
            "bankroll_after": after,
        }
    )


def test_summary_breakeven():
    led = _ledger([10.0, -10.0], [10.0, 10.0], [0.01, -0.01])
    s = summary(led)
    assert s["n_bets"] == 2
    assert s["profit"] == 0.0
    assert s["yield"] == 0.0


def test_max_drawdown():
    assert max_drawdown([1000, 1100, 900, 950]) == (900 - 1100) / 1100


def test_max_drawdown_monotone_up_is_zero():
    assert max_drawdown([100, 110, 120]) == 0.0


def test_bootstrap_ci_deterministic():
    x = np.array([0.1, -0.2, 0.3, -0.1, 0.05])
    assert bootstrap_ci(x, seed=42) == bootstrap_ci(x, seed=42)


def test_clv_beat_rate_ignores_nan():
    led = _ledger([1, 1, 1], [1, 1, 1], [0.1, -0.1, float("nan")])
    s = summary(led)
    assert s["n_with_clv"] == 2
    assert s["clv_beat_rate"] == 0.5


def test_verdict_too_few():
    assert "Too few" in verdict({"n_bets": 5, "yield_ci": [0.0, 0.0]})


def test_verdict_negative():
    v = verdict({"n_bets": 100, "yield_ci": [-0.1, -0.02]})
    assert "loses to the vig" in v


def test_verdict_straddles_zero():
    v = verdict({"n_bets": 100, "yield_ci": [-0.05, 0.05]})
    assert "no evidence of an edge" in v


def test_verdict_positive():
    v = verdict({"n_bets": 100, "yield_ci": [0.02, 0.10]})
    assert "profitable in-sample" in v


def test_empty_ledger_summary():
    s = summary(pd.DataFrame(columns=["pnl", "stake", "clv", "bankroll_after"]))
    assert s["n_bets"] == 0
