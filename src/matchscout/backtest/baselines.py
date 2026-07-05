"""Naive betting baselines (council-required benchmarks).

Every strategy result is compared against betting the same market blindly: always-home,
always-favorite (shortest 1X2 price), always-over-2.5. These bet every match at the Bet365
pre-match price, so `settle_bets` scores them exactly like the model's value bets.
"""

from __future__ import annotations

import pandas as pd


def baseline_picks(
    matches: pd.DataFrame, odds: pd.DataFrame, strategy: str, *, book: str = "B365"
) -> pd.DataFrame:
    """Picks (match_id, market, selection, p_model, odds) for a naive baseline strategy."""
    pre = odds[(odds["book"] == book) & (~odds["is_closing"].astype(bool))]
    played_ids = set(matches[matches["status"] == "played"]["match_id"])

    if strategy == "home":
        picks = pre[(pre["market"] == "1x2") & (pre["selection"] == "H")]
    elif strategy == "over":
        picks = pre[(pre["market"] == "ou25") & (pre["selection"] == "over")]
    elif strategy == "favorite":
        one_x_two = pre[pre["market"] == "1x2"]
        picks = one_x_two.loc[one_x_two.groupby("match_id")["odds"].idxmin()]
    else:
        raise ValueError(f"unknown baseline strategy {strategy!r}")

    picks = picks[picks["match_id"].isin(played_ids)].copy()
    picks["p_model"] = 1.0 / picks["odds"]
    return picks[["match_id", "market", "selection", "p_model", "odds"]].reset_index(drop=True)
