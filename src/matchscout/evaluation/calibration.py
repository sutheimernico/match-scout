"""Model-vs-market calibration report for 1X2 predictions.

Compares the goal model's walk-forward probabilities against the market benchmark — the
Shin-de-vigged Pinnacle closing line (council D5/D6) — on strictly-proper scores (Brier,
log-loss). The verdict is rule-generated: the honest, expected finding is that the closing
line is better calibrated and the model does NOT beat it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from matchscout.evaluation.metrics import brier_score, log_loss
from matchscout.value.devig import devig_shin

_1X2 = ["H", "D", "A"]
_CLASS = {"H": 0, "D": 1, "A": 2}


def market_probs_1x2(
    odds: pd.DataFrame, method: Callable[[np.ndarray], np.ndarray] = devig_shin
) -> dict[str, np.ndarray]:
    """Per-match de-vigged Pinnacle-closing 1X2 probabilities (the market benchmark)."""
    closing = odds[(odds["book"] == "PS") & (odds["is_closing"]) & (odds["market"] == "1x2")]
    out: dict[str, np.ndarray] = {}
    for match_id, group in closing.groupby("match_id"):
        prices = dict(zip(group["selection"], group["odds"], strict=False))
        if all(sel in prices for sel in _1X2):
            out[str(match_id)] = method(np.array([prices[s] for s in _1X2], dtype=float))
    return out


def calibration_report(
    preds: pd.DataFrame,
    odds: pd.DataFrame,
    method: Callable[[np.ndarray], np.ndarray] = devig_shin,
) -> dict:
    """Brier + log-loss for the model vs. the closing-line benchmark, with a verdict."""
    market = market_probs_1x2(odds, method)
    rows = preds[preds["match_id"].isin(market)]
    if rows.empty:
        raise ValueError("no matches with both model predictions and closing-line odds")

    y = rows["outcome_1x2"].map(_CLASS).to_numpy()
    model_p = rows[["p_H", "p_D", "p_A"]].to_numpy(dtype=float)
    market_p = np.array([market[m] for m in rows["match_id"]])

    report = {
        "n": int(len(rows)),
        "model": {"brier": brier_score(model_p, y), "log_loss": log_loss(model_p, y)},
        "market": {"brier": brier_score(market_p, y), "log_loss": log_loss(market_p, y)},
    }
    beats = (
        report["model"]["brier"] < report["market"]["brier"]
        and report["model"]["log_loss"] < report["market"]["log_loss"]
    )
    report["beats_closing_line"] = bool(beats)
    report["verdict"] = (
        "Model beats the closing line on both Brier and log-loss."
        if beats
        else "Model does NOT beat the closing line (expected) — the market is better calibrated."
    )
    return report
