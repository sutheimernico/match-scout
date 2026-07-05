"""Stake sizing: flat and fractional-Kelly (council D10).

Flat staking is the HEADLINE (order-independent, robust). Kelly is a secondary illustrative
track: it uses a fraction of full Kelly on a (optionally shrunk) edge and a hard per-bet cap,
because a raw edge estimate carries real error (optimizer's curse) and full Kelly on it
over-bets. Both take the with-vig decimal odds the bet is actually placed at.
"""

from __future__ import annotations


def flat_stake(unit: float = 1.0) -> float:
    """Constant stake per bet (the headline scheme)."""
    return unit


def kelly_full(prob: float, odds: float) -> float:
    """Full-Kelly fraction of bankroll: (p*odds - 1) / (odds - 1), floored at 0."""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, (prob * odds - 1.0) / b)


def kelly_stake(
    prob: float,
    odds: float,
    bankroll: float,
    *,
    fraction: float = 0.25,
    cap: float = 0.05,
    edge_shrink: float = 1.0,
) -> float:
    """Fractional-Kelly stake (absolute units) with edge shrinkage and a hard per-bet cap.

    `fraction` is the Kelly fraction (<=0.25 recommended), `cap` bounds the stake to a share
    of bankroll, `edge_shrink` (<=1) discounts the edge to counter the optimizer's curse (D10).
    """
    b = odds - 1.0
    if b <= 0:
        return 0.0
    edge = edge_shrink * (prob * odds - 1.0)
    kelly_f = max(0.0, edge / b)
    staked_fraction = min(fraction * kelly_f, cap)
    return staked_fraction * bankroll
