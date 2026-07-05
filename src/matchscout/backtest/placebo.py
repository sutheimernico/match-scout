"""Market-truth Monte-Carlo null (council D3, corrected per methodology review).

An earlier version shuffled real outcomes globally across matches; the methodology reviewer
showed that ignores each match's market-implied difficulty — value bets skew to underdog/long-
odds selections, so borrowing the favourite-dominated population base rate inflated the null to
+18.8% yield (it could have hidden a large leak).

The corrected null simulates each bet's outcome from the market's OWN de-vigged closing
probability for that selection. If the closing line is the truth, betting at the taken price
yields ~= the CLV. A genuine edge makes the observed yield exceed this null; no edge leaves the
observed yield inside it. This ties the leak guard directly to the (independently-correct) CLV.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from matchscout.backtest.engine import closing_probs, settle_bets
from matchscout.backtest.metrics import summary
from matchscout.value.devig import devig_shin


def market_null_test(
    picks: pd.DataFrame,
    matches: pd.DataFrame,
    odds: pd.DataFrame,
    *,
    n: int = 1000,
    seed: int = 0,
    flat_unit: float = 10.0,
    method: Callable[[np.ndarray], np.ndarray] = devig_shin,
) -> dict:
    """Compare the real flat-stake yield against the market-implied (closing-line) null."""
    real_yield = summary(
        settle_bets(picks, matches, odds, staking="flat", flat_unit=flat_unit)
    ).get("yield", float("nan"))

    closing = closing_probs(odds, method)
    p_null, taken = [], []
    for row in picks.itertuples():
        p = closing.get((row.match_id, row.market, row.selection))
        if p is not None:
            p_null.append(p)
            taken.append(row.odds)

    if not p_null:
        return {
            "real_yield": float(real_yield), "null_mean_yield": float("nan"),
            "null_std_yield": float("nan"), "real_exceeds_null_95pct": False, "n_bets": 0,
        }

    p_arr = np.asarray(p_null, dtype=float)
    odds_arr = np.asarray(taken, dtype=float)
    rng = np.random.default_rng(seed)
    wins = rng.random((n, len(p_arr))) < p_arr
    pnl = np.where(wins, flat_unit * (odds_arr - 1.0), -flat_unit)
    ys = pnl.sum(axis=1) / (flat_unit * len(p_arr))
    return {
        "real_yield": float(real_yield),
        "null_mean_yield": float(ys.mean()),
        "null_std_yield": float(ys.std()),
        "real_exceeds_null_95pct": bool(real_yield > np.quantile(ys, 0.95)),
        "n_bets": int(len(p_arr)),
        "n_draws": n,
    }
