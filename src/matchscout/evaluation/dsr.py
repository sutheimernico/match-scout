"""Deflated-Sharpe-Ratio hurdle over the trial log — the D1 significance bar.

The problem this closes: with enough tried configurations, *something* looks profitable. The
plain bootstrap CI in `backtest/metrics.py` answers "could this one result be luck?"; it does
not answer "could the best of N tried results be luck?". The Deflated Sharpe Ratio (Bailey &
Lopez de Prado, 2014) does: it raises the bar by the expected maximum Sharpe ratio that N
independent zero-edge trials would produce anyway, then asks whether the observed Sharpe still
clears it.

Adapted to betting, one "observation" is one settled bet and its return is `pnl / stake`, so
the Sharpe ratio is per bet (not annualized) and T is the bet count:

    SR0  = sqrt(V[SR]) * [ (1 - g) * Z^-1(1 - 1/N) + g * Z^-1(1 - 1/(N*e)) ]
    DSR  = Z[ (SR - SR0) * sqrt(T - 1) / sqrt(1 - skew*SR + (kurtosis - 1)/4 * SR^2) ]

with g = the Euler-Mascheroni constant, N = number of trials, T = number of bets.

`V[SR]` is the variance of the Sharpe ratios across the logged trials; with fewer than two
logged Sharpes it falls back to the null sampling variance 1/(T-1). DSR is read as the
probability that the true Sharpe is positive *after* accounting for the search; the hurdle is
DSR > 0.95 (i.e. adjusted p < 0.05).

Deliberately NOT implemented: the PBO (probability of backtest overfitting) companion statistic
— it needs combinatorially split backtest paths, which this harness does not produce. The trial
count is the honest thing available, and it is the one that grows automatically.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import kurtosis as _kurtosis
from scipy.stats import norm
from scipy.stats import skew as _skew

EULER_MASCHERONI = 0.5772156649015329
HURDLE = 0.95


def sharpe_ratio(returns) -> float:
    """Per-bet Sharpe ratio: mean return over its standard deviation (0 risk-free rate)."""
    r = np.asarray(returns, dtype=float)
    if len(r) < 2:
        return float("nan")
    sd = float(r.std(ddof=1))
    if sd == 0.0:
        return float("nan")
    return float(r.mean() / sd)


def expected_max_sharpe(n_trials: int, sr_std: float) -> float:
    """Expected maximum Sharpe ratio of `n_trials` independent zero-edge trials.

    With a single trial there is no selection bias, so the bar stays at 0.
    """
    if n_trials <= 1 or not math.isfinite(sr_std) or sr_std <= 0:
        return 0.0
    z1 = norm.ppf(1.0 - 1.0 / n_trials)
    z2 = norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(sr_std * ((1.0 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2))


def deflated_sharpe(returns, *, n_trials: int, sr_std: float | None = None) -> dict:
    """DSR of a per-bet return series against a search of `n_trials` configurations.

    `sr_std` is the spread of Sharpe ratios across those trials; when unknown it falls back to
    the null sampling deviation 1/sqrt(T-1).
    """
    r = np.asarray(returns, dtype=float)
    n = int(len(r))
    sr = sharpe_ratio(r)
    out: dict = {
        "n_bets": n,
        "n_trials": int(n_trials),
        "sharpe": sr,
        "sr_std": sr_std,
        "expected_max_sharpe": float("nan"),
        "dsr": float("nan"),
        "hurdle_met": False,
    }
    if n < 3 or not math.isfinite(sr):
        return out

    if sr_std is None or not math.isfinite(sr_std) or sr_std <= 0:
        sr_std = 1.0 / math.sqrt(n - 1)
        out["sr_std"] = sr_std
        out["sr_std_source"] = "null-sampling-fallback"
    else:
        out["sr_std_source"] = "observed-across-trials"

    sr0 = expected_max_sharpe(n_trials, sr_std)
    skew = float(_skew(r, bias=False))
    kurt = float(_kurtosis(r, fisher=False, bias=False))  # non-excess: 3.0 for a normal
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2
    if denom <= 0:
        return {**out, "expected_max_sharpe": sr0, "skew": skew, "kurtosis": kurt}

    dsr = float(norm.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(denom)))
    return {
        **out,
        "expected_max_sharpe": sr0,
        "skew": skew,
        "kurtosis": kurt,
        "dsr": dsr,
        "hurdle_met": bool(dsr > HURDLE),
    }


def hurdle_verdict(result: dict) -> str:
    """One rule-generated sentence: does the result clear the trials-adjusted bar?"""
    n_trials = result.get("n_trials", 0)
    dsr = result.get("dsr", float("nan"))
    if not math.isfinite(dsr):
        return (
            f"Too few settled bets for a trials-adjusted verdict "
            f"(n={result.get('n_bets', 0)}, trials={n_trials})."
        )
    sr = result["sharpe"]
    sr0 = result["expected_max_sharpe"]
    lead = (
        f"An edge claim needs DSR > {HURDLE:.2f} across {n_trials} logged "
        f"trial{'s' if n_trials != 1 else ''} — current DSR {dsr:.3f} "
        f"(per-bet Sharpe {sr:.4f} vs. a {sr0:.4f} bar from the search)."
    )
    if result.get("hurdle_met"):
        return lead + " Hurdle MET — treat with the usual skepticism: check CLV and out-of-sample."
    return lead + " Hurdle NOT met — no edge survives the multiple-trials correction."
