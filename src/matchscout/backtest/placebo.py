"""Label-permutation placebo test (council D3).

Shuffle match outcomes among matches and re-settle the same bets. A genuine edge survives the
permutation; selection/leakage artifacts collapse to noise. If the real yield does not exceed
the placebo distribution, there is no edge (the expected honest finding). If it far exceeds the
placebo — investigate a leak before believing it. This is the leak guard the powerless
one-matchday shift-test could not provide.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from matchscout.backtest.engine import settle_bets
from matchscout.backtest.metrics import summary


def _shuffle_outcomes(matches: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    shuffled = matches.copy().reset_index(drop=True)
    played_idx = shuffled.index[shuffled["status"] == "played"].to_numpy()
    perm = rng.permutation(played_idx)
    goals = shuffled.loc[perm, ["ft_home_goals", "ft_away_goals"]].to_numpy()
    shuffled.loc[played_idx, ["ft_home_goals", "ft_away_goals"]] = goals
    return shuffled


def placebo_test(
    picks: pd.DataFrame,
    matches: pd.DataFrame,
    odds: pd.DataFrame,
    *,
    n: int = 25,
    seed: int = 0,
    flat_unit: float = 10.0,
) -> dict:
    """Compare the real flat-stake yield against a distribution of label-permuted yields."""
    rng = np.random.default_rng(seed)
    real_yield = summary(
        settle_bets(picks, matches, odds, staking="flat", flat_unit=flat_unit)
    ).get("yield", float("nan"))

    placebo_yields = []
    for _ in range(n):
        shuffled = _shuffle_outcomes(matches, rng)
        ledger = settle_bets(picks, shuffled, odds, staking="flat", flat_unit=flat_unit)
        placebo_yields.append(summary(ledger).get("yield", float("nan")))
    pa = np.asarray(placebo_yields, dtype=float)
    return {
        "real_yield": float(real_yield),
        "placebo_mean_yield": float(np.nanmean(pa)),
        "placebo_std_yield": float(np.nanstd(pa)),
        "real_exceeds_placebo_95pct": bool(real_yield > np.nanquantile(pa, 0.95)),
        "n_permutations": n,
    }
