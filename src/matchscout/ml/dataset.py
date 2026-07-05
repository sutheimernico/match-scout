"""Feature dataset for the walled-off 1X2 ML challenger.

Features are pre-match and point-in-time by construction: the Dixon-Coles walk-forward
probabilities (already leak-free) plus the Shin-de-vigged market closing probabilities. The
market feature is deliberately included — per council D11 this makes "beats Dixon-Coles" nearly
automatic and uninteresting; only "beats the closing line" is the real test, so the challenger is
judged on the market, not on DC.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from matchscout.evaluation.calibration import market_probs_1x2
from matchscout.value.devig import devig_shin

FEATURE_COLUMNS = ["dc_H", "dc_D", "dc_A", "dc_over", "dc_under", "mkt_H", "mkt_D", "mkt_A"]
_CLASS = {"H": 0, "D": 1, "A": 2}


def build_1x2_dataset(
    preds: pd.DataFrame,
    odds: pd.DataFrame,
    method: Callable[[np.ndarray], np.ndarray] = devig_shin,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Return (X features, y class labels 0/1/2, match_ids) for matches with model + market."""
    market = market_probs_1x2(odds, method)
    rows = preds[preds["match_id"].isin(market)].copy()
    if rows.empty:
        raise ValueError("no matches with both model predictions and closing-line odds")

    m = np.array([market[mid] for mid in rows["match_id"]])
    features = pd.DataFrame(
        {
            "dc_H": rows["p_H"].to_numpy(dtype=float),
            "dc_D": rows["p_D"].to_numpy(dtype=float),
            "dc_A": rows["p_A"].to_numpy(dtype=float),
            "dc_over": rows["p_over"].to_numpy(dtype=float),
            "dc_under": rows["p_under"].to_numpy(dtype=float),
            "mkt_H": m[:, 0],
            "mkt_D": m[:, 1],
            "mkt_A": m[:, 2],
        }
    )
    y = rows["outcome_1x2"].map(_CLASS).to_numpy()
    return features, y, rows["match_id"].to_numpy()
