"""Backtest metrics + rule-generated verdict (council D2).

Yield (= ROI = profit / turnover) is reported with a bootstrap confidence interval, never as a
bare point estimate. CLV mean + beat-rate are first-class (the leakage-resistant skill signal).
The verdict is generated from the CI, not asserted: the honest, expected outcome is a yield CI
that straddles or sits below 0. Bootstrap is seeded for determinism.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _returns(ledger: pd.DataFrame) -> np.ndarray:
    return (ledger["pnl"] / ledger["stake"]).to_numpy(dtype=float)


def max_drawdown(bankroll) -> float:
    """Largest peak-to-trough fractional drop of the bankroll curve (<= 0)."""
    b = np.asarray(bankroll, dtype=float)
    if len(b) == 0:
        return 0.0
    peak = np.maximum.accumulate(b)
    return float(((b - peak) / peak).min())


def bootstrap_ci(x, *, n: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    """Bootstrap CI for the mean of `x` (deterministic given `seed`)."""
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    resamples = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    lo, hi = np.quantile(resamples, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def summary(ledger: pd.DataFrame) -> dict:
    """Headline backtest metrics for a settled ledger."""
    if ledger.empty:
        return {"n_bets": 0, "yield": float("nan"), "yield_ci": [float("nan"), float("nan")]}

    returns = _returns(ledger)
    staked = float(ledger["stake"].sum())
    profit = float(ledger["pnl"].sum())
    clv = ledger["clv"].to_numpy(dtype=float)
    clv_finite = clv[np.isfinite(clv)]
    lo, hi = bootstrap_ci(returns)
    return {
        "n_bets": int(len(ledger)),
        "total_staked": staked,
        "profit": profit,
        "yield": profit / staked if staked else float("nan"),
        "yield_ci": [lo, hi],
        "final_bankroll": float(ledger["bankroll_after"].iloc[-1]),
        "max_drawdown": max_drawdown(ledger["bankroll_after"]),
        "clv_mean": float(clv_finite.mean()) if len(clv_finite) else float("nan"),
        "clv_beat_rate": float((clv_finite > 0).mean()) if len(clv_finite) else float("nan"),
        "n_with_clv": int(len(clv_finite)),
    }


def verdict(summ: dict) -> str:
    """Rule-generated verdict from the yield confidence interval."""
    if summ["n_bets"] < 30:
        return f"Too few bets for a verdict (n={summ['n_bets']} < 30)."
    lo, hi = summ["yield_ci"]
    if lo > 0:
        return (
            f"Positive yield, 95% CI [{lo:.3f}, {hi:.3f}] excludes 0 — profitable in-sample. "
            "Treat with skepticism: check CLV beat-rate and the trial count before believing it."
        )
    if hi < 0:
        return (
            f"Negative yield, 95% CI [{lo:.3f}, {hi:.3f}] below 0 — "
            "loses to the vig, as expected."
        )
    return (
        f"Yield 95% CI [{lo:.3f}, {hi:.3f}] straddles 0 — no evidence of an edge "
        "(the expected honest finding)."
    )
