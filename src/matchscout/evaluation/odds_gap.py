"""How far prices move between the price the harness takes and the price it is judged by (D7).

Closing-line value (CLV) — the project's headline benchmark — compares the pre-match price a bet
was taken at with the closing price. That only measures anything if the line actually moves
between the two. If the pre-match and closing columns were near-identical, "beating the close"
would be a coin flip dressed up as signal, and the project would have to say so.

This module measures it: for every match and market, both prices are Shin de-vigged and the
per-selection probability gap `p_ref_close - p_B365_pre` is taken. Three reference closes:

- `B365` close — the same book at kickoff: pure line movement, no cross-book noise;
- `PS` close — Pinnacle, the backtest's CLV benchmark (movement + the sharp book's opinion);
- `Avg` close — the market average, the forward loop's fallback now that the source no longer
  carries Pinnacle in current-season files.

Gaps are in probability points (0.01 = 1 pp). A segment whose median absolute gap is below
`WEAK_MEDIAN_PP` is labelled `weak`: CLV there is mostly comparing a price with itself.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from matchscout.value.devig import devig_shin

TAKEN_BOOK = "B365"
REFERENCE_BOOKS = ("B365", "PS", "Avg")
_ORDER = {"1x2": ("H", "D", "A"), "ou25": ("over", "under")}

# Half a probability point. Below it, a "beat the close" is within rounding of the quoted odds
# (a 2.00 vs. 2.02 price is ~0.5 pp) — too small to carry information about the bet.
WEAK_MEDIAN_PP = 0.005


def _devigged(odds: pd.DataFrame, book: str, closing: bool) -> pd.DataFrame:
    rows = odds[(odds["book"] == book) & (odds["is_closing"].astype(bool) == closing)]
    out = []
    for (match_id, market), group in rows.groupby(["match_id", "market"]):
        order = _ORDER.get(str(market))
        prices = dict(zip(group["selection"], group["odds"], strict=False))
        if order is None or not all(sel in prices for sel in order):
            continue
        probs = devig_shin(np.array([prices[s] for s in order], dtype=float))
        out += [
            {"match_id": match_id, "market": market, "selection": s, "p": float(p)}
            for s, p in zip(order, probs, strict=True)
        ]
    return pd.DataFrame(out, columns=["match_id", "market", "selection", "p"])


def price_gaps(odds: pd.DataFrame, competition_of: dict[str, str]) -> pd.DataFrame:
    """One row per (match, market, selection, reference book): the de-vigged probability gap."""
    taken = _devigged(odds, TAKEN_BOOK, closing=False)
    frames = []
    for ref in REFERENCE_BOOKS:
        close = _devigged(odds, ref, closing=True)
        joined = taken.merge(
            close, on=["match_id", "market", "selection"], suffixes=("_pre", "_close")
        )
        joined["reference"] = ref
        frames.append(joined)
    gaps = pd.concat(frames, ignore_index=True)
    gaps["gap"] = gaps["p_close"] - gaps["p_pre"]
    gaps["competition"] = gaps["match_id"].map(competition_of)
    return gaps


def _stats(abs_gap: pd.Series) -> dict:
    median = float(abs_gap.median())
    return {
        "n": int(len(abs_gap)),
        "mean_abs_pp": round(float(abs_gap.mean()) * 100, 2),
        "median_abs_pp": round(median * 100, 2),
        "p90_abs_pp": round(float(abs_gap.quantile(0.9)) * 100, 2),
        "share_moved_1pp": round(float((abs_gap >= 0.01).mean()), 3),
        "clv_signal": "weak" if median < WEAK_MEDIAN_PP else "informative",
    }


def gap_report(gaps: pd.DataFrame, group_by: Iterable[str]) -> list[dict]:
    """Distribution of |gap| per segment, with a rule-generated weak/informative label."""
    keys = list(group_by)
    out = []
    for key, group in gaps.groupby(keys):
        values = key if isinstance(key, tuple) else (key,)
        out.append({**dict(zip(keys, values, strict=True)), **_stats(group["gap"].abs())})
    return out


def findings(pooled: list[dict]) -> list[str]:
    """Plain-language one-liners per market x reference, generated from the numbers."""
    lines = []
    for row in pooled:
        verdict = (
            "CLV is a meaningful yardstick here"
            if row["clv_signal"] == "informative"
            else "CLV is a WEAK yardstick here — prices barely move"
        )
        lines.append(
            f"{row['market']} vs. {row['reference']} close: median |Δp| "
            f"{row['median_abs_pp']:.2f} pp, {row['share_moved_1pp']:.0%} of prices move ≥1 pp "
            f"(n={row['n']}) — {verdict}."
        )
    return lines
