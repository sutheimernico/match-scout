"""Value-bet edge and selection.

The edge is the expected value per unit stake on the real (with-vig) price:

    edge = p_model * odds - 1

This is the SOLE selection criterion (council D6) — the margin already lives in the odds, so
no de-vig is applied here. Bets are priced at a single a-priori-fixed book's pre-match price
(Bet365 by default, D5); closing odds are never a selection input. A bet is "value" when its
edge exceeds a threshold.
"""

from __future__ import annotations

import pandas as pd

_PRED_MAP = {
    "p_H": ("1x2", "H"),
    "p_D": ("1x2", "D"),
    "p_A": ("1x2", "A"),
    "p_over": ("ou25", "over"),
    "p_under": ("ou25", "under"),
}


def edge(p_model, odds):
    """Expected value per unit stake at decimal `odds` given model probability `p_model`."""
    return p_model * odds - 1.0


def _melt_predictions(preds: pd.DataFrame) -> pd.DataFrame:
    long = preds.melt(
        id_vars=["match_id"],
        value_vars=list(_PRED_MAP),
        var_name="col",
        value_name="p_model",
    )
    long["market"] = long["col"].map(lambda c: _PRED_MAP[c][0])
    long["selection"] = long["col"].map(lambda c: _PRED_MAP[c][1])
    return long[["match_id", "market", "selection", "p_model"]]


def select_value_bets(
    preds: pd.DataFrame,
    odds: pd.DataFrame,
    *,
    threshold: float = 0.0,
    book: str = "B365",
) -> pd.DataFrame:
    """Value bets where `edge > threshold`, priced at `book`'s pre-match odds.

    Returns match_id, market, selection, p_model, odds, edge — sorted by edge descending.
    """
    long_preds = _melt_predictions(preds)
    prices = odds[(odds["book"] == book) & (~odds["is_closing"].astype(bool))][
        ["match_id", "market", "selection", "odds"]
    ]
    merged = long_preds.merge(prices, on=["match_id", "market", "selection"], how="inner")
    merged["edge"] = edge(merged["p_model"], merged["odds"])
    picks = merged[merged["edge"] > threshold]
    return picks.sort_values("edge", ascending=False).reset_index(drop=True)
