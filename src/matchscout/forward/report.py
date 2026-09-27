"""The forward track record as numbers a page can show without overselling a small sample.

Paper stakes only. Two independent records, both read from the committed event logs:

- **Bets** (`data/bets.jsonl`): yield with a bootstrap CI, CLV and its beat-rate, the book the
  CLV was measured against, and the cumulative-profit curve. Same metric definitions as the
  backtest (`backtest.metrics.summary`), so forward and backtest numbers are comparable.
- **Predictions** (`data/predictions.jsonl`): model vs. market Brier score on every settled
  fixture that had a price — the larger, unselected sample. The difference comes with a paired
  bootstrap CI, so "the model was better this month" cannot be read off twelve matches.

Every block carries `n`, and every verdict is rule-generated: below `MIN_N` it says so.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from matchscout.backtest.metrics import bootstrap_ci, summary, verdict
from matchscout.forward.ledger import NO_ODDS, PENDING, SETTLED, VOID
from matchscout.forward.loop import settled_ledger

MIN_N = 30  # same floor as backtest.metrics.verdict
_RESULT_INDEX = {"H": 0, "D": 1, "A": 2}


def _clean(value: Any) -> Any:
    """NaN/inf -> None, recursively: the output is read by `JSON.parse`, which rejects NaN."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if isinstance(value, float | np.floating):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def bets_record(bets: pd.DataFrame, start_bankroll: float = 1000.0) -> dict[str, Any]:
    statuses = Counter(bets["status"]) if not bets.empty else Counter()
    ledger = settled_ledger(bets, start_bankroll)
    record = summary(ledger)
    curve = [
        {"date": str(r.date)[:10], "profit": round(float(r.bankroll_after) - start_bankroll, 2)}
        for r in ledger.itertuples()
    ]
    return {
        **record,
        "n_won": int(ledger["won"].astype(bool).sum()) if not ledger.empty else 0,
        "n_pending": statuses[PENDING],
        "n_void": statuses[VOID],
        "n_no_odds": statuses[NO_ODDS],
        "clv_books": dict(Counter(ledger["clv_book"].dropna())) if not ledger.empty else {},
        "verdict": verdict(record),
        "curve": curve,
    }


def calibration_record(predictions: pd.DataFrame) -> dict[str, Any]:
    """Model vs. market multiclass Brier on settled, priced fixtures (1X2)."""
    cols_model, cols_market = ["p_H", "p_D", "p_A"], ["mkt_H", "mkt_D", "mkt_A"]
    if predictions.empty:
        done = predictions
    else:
        done = predictions[predictions["status"] == SETTLED].dropna(subset=cols_market)
    n = int(len(done))
    if n == 0:
        return {"n": 0, "verdict": "No settled, priced predictions yet."}

    y = done["result"].map(_RESULT_INDEX).to_numpy(dtype=int)
    onehot = np.eye(3)[y]
    model = done[cols_model].to_numpy(dtype=float)
    market = done[cols_market].to_numpy(dtype=float)
    brier_model = ((model - onehot) ** 2).sum(axis=1)
    brier_market = ((market - onehot) ** 2).sum(axis=1)
    diff = brier_model - brier_market  # < 0 = model better
    lo, hi = bootstrap_ci(diff)

    if n < MIN_N:
        text = f"Too few settled predictions for a verdict (n={n} < {MIN_N})."
    elif hi < 0:
        text = "Model better calibrated than the market — CI excludes 0. Check before believing."
    elif lo > 0:
        text = "Market better calibrated than the model — CI excludes 0 (the expected finding)."
    else:
        text = "No measurable calibration difference between model and market yet."
    return {
        "n": n,
        "brier_model": float(brier_model.mean()),
        "brier_market": float(brier_market.mean()),
        "brier_diff": float(diff.mean()),
        "brier_diff_ci": [lo, hi],
        "hit_rate_model": float((model.argmax(axis=1) == y).mean()),
        "hit_rate_market": float((market.argmax(axis=1) == y).mean()),
        "verdict": text,
    }


def forward_record(
    bets: pd.DataFrame, predictions: pd.DataFrame, *, start_bankroll: float = 1000.0
) -> dict[str, Any]:
    """Everything the forward surfaces show. `state` drives the empty/pending/settled views."""
    stamps = [
        s
        for frame in (bets, predictions)
        if not frame.empty
        for s in frame["timestamp_known"].dropna()
    ]
    betting = bets_record(bets, start_bankroll)
    calibration = calibration_record(predictions)
    if not stamps:
        state = "empty"
    elif betting["n_bets"] == 0 and calibration["n"] == 0:
        state = "pending"
    else:
        state = "settled"
    return _clean(
        {
            "state": state,
            "since": min(stamps)[:10] if stamps else None,
            "start_bankroll": start_bankroll,
            "bets": betting,
            "calibration": calibration,
        }
    )
