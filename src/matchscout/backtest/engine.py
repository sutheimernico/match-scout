"""Settle value bets into a bankroll ledger.

Each bet is settled at the price it was TAKEN (Bet365 pre-match, council D4) — the closing
line is used only to compute closing-line value (CLV), never as a settlement price. CLV per
bet is `p_close * odds_taken - 1`, where `p_close` is the Shin-de-vigged Pinnacle closing
probability for that selection: positive means you took a better price than the market's
closing fair value. Flat staking is bankroll-independent (order-free); Kelly is sequential.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from matchscout.backtest.staking import kelly_stake
from matchscout.value.devig import devig_shin

_ORDER = {"1x2": ["H", "D", "A"], "ou25": ["over", "under"]}

LEDGER_COLUMNS = [
    "match_id", "date", "market", "selection", "odds_taken",
    "stake", "won", "pnl", "bankroll_after", "clv", "clv_beat",
]


def _match_outcomes(matches: pd.DataFrame) -> pd.DataFrame:
    played = matches[matches["status"] == "played"]
    hg = played["ft_home_goals"].astype(int).to_numpy()
    ag = played["ft_away_goals"].astype(int).to_numpy()
    return pd.DataFrame(
        {
            "match_id": played["match_id"].to_numpy(),
            "date": pd.to_datetime(played["date"]).to_numpy(),
            "outcome_1x2": np.where(hg > ag, "H", np.where(hg < ag, "A", "D")),
            "outcome_ou": np.where((hg + ag) >= 3, "over", "under"),
        }
    )


def closing_probs(
    odds: pd.DataFrame,
    method: Callable[[np.ndarray], np.ndarray],
    book: str = "PS",
) -> dict[tuple[str, str, str], float]:
    """De-vigged closing probabilities per (match_id, market, selection) for one book.

    Pinnacle (`PS`) is the default and the sharpest reference. It is a parameter because the
    source dropped Pinnacle from its current-season files (verified 2026-09-20), so the forward
    loop has to fall back to the next-best closing book and record which one it used.
    """
    closing = odds[(odds["book"] == book) & (odds["is_closing"].astype(bool))]
    out: dict[tuple[str, str, str], float] = {}
    for (match_id, market), group in closing.groupby(["match_id", "market"]):
        order = _ORDER.get(str(market))
        if order is None:
            continue
        prices = dict(zip(group["selection"], group["odds"], strict=False))
        if not all(sel in prices for sel in order):
            continue
        probs = method(np.array([prices[s] for s in order], dtype=float))
        for sel, prob in zip(order, probs, strict=True):
            out[(str(match_id), str(market), sel)] = float(prob)
    return out


def settle_bets(
    picks: pd.DataFrame,
    matches: pd.DataFrame,
    odds: pd.DataFrame,
    *,
    staking: str = "flat",
    start_bankroll: float = 1000.0,
    flat_unit: float = 10.0,
    kelly_fraction: float = 0.25,
    kelly_cap: float = 0.05,
    edge_shrink: float = 1.0,
    method: Callable[[np.ndarray], np.ndarray] = devig_shin,
) -> pd.DataFrame:
    """Settle `picks` chronologically into a bankroll ledger (see LEDGER_COLUMNS)."""
    if picks.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in LEDGER_COLUMNS})

    df = picks.merge(_match_outcomes(matches), on="match_id", how="inner").sort_values("date")
    closing = closing_probs(odds, method)

    bankroll = start_bankroll
    rows = []
    for r in df.itertuples():
        actual = r.outcome_1x2 if r.market == "1x2" else r.outcome_ou
        won = bool(r.selection == actual)
        stake = flat_unit if staking == "flat" else kelly_stake(
            r.p_model, r.odds, bankroll,
            fraction=kelly_fraction, cap=kelly_cap, edge_shrink=edge_shrink,
        )
        pnl = stake * (r.odds - 1.0) if won else -stake
        bankroll += pnl
        p_close = closing.get((r.match_id, r.market, r.selection))
        clv = (p_close * r.odds - 1.0) if p_close is not None else float("nan")
        rows.append(
            {
                "match_id": r.match_id, "date": r.date, "market": r.market,
                "selection": r.selection, "odds_taken": r.odds, "stake": stake,
                "won": won, "pnl": pnl, "bankroll_after": bankroll,
                "clv": clv, "clv_beat": (clv > 0) if p_close is not None else False,
            }
        )
    return pd.DataFrame(rows)
