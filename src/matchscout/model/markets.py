"""Derive betting-market probabilities from a goal-model scoreline distribution.

Everything here is a goals-only market — computable from the score-probability matrix and thus
legitimately priceable by the Dixon-Coles model. Player markets (goalscorers) and event markets
(corners, cards) are NOT here: they need player/event data the free stack does not have.

`to_advance` is the knockout "to qualify" market and is deliberately different from the 90-minute
1X2 result: a regulation draw goes to extra time, then penalties (~50/50) — so a team's chance to
ADVANCE is higher than its chance to win in 90 minutes. (Single-match knockouts, e.g. World Cup;
two-legged ties are not modelled.)
"""

from __future__ import annotations

import numpy as np

from matchscout.model.poisson import score_matrix

STANDARD_OU_LINES = (0.5, 1.5, 2.5, 3.5, 4.5)


def over_under(matrix: np.ndarray, line: float) -> tuple[float, float]:
    """(P(over line), P(under line)) total goals. Half-lines only, so no push."""
    idx = np.arange(matrix.shape[0])
    totals = np.add.outer(idx, idx)
    over = float(matrix[totals > line].sum())
    return over, 1.0 - over


def all_over_under(matrix: np.ndarray, lines=STANDARD_OU_LINES) -> dict[float, float]:
    """P(over) for each standard total-goals line."""
    return {line: over_under(matrix, line)[0] for line in lines}


def btts(matrix: np.ndarray) -> tuple[float, float]:
    """(P(both teams score), P(not)) — both margins >= 1 goal."""
    yes = float(matrix[1:, 1:].sum())
    return yes, 1.0 - yes


def correct_score(matrix: np.ndarray, top_n: int = 5) -> list[tuple[str, float]]:
    """The `top_n` most likely exact scorelines as ("h-a", prob), highest first."""
    scores = [
        (f"{i}-{j}", float(matrix[i, j]))
        for i in range(matrix.shape[0])
        for j in range(matrix.shape[1])
    ]
    scores.sort(key=lambda kv: kv[1], reverse=True)
    return scores[:top_n]


def double_chance(matrix: np.ndarray) -> dict[str, float]:
    """Double-chance probabilities: 1X (home or draw), 12 (home or away), X2 (draw or away)."""
    home = float(np.tril(matrix, -1).sum())
    draw = float(np.trace(matrix))
    away = float(np.triu(matrix, 1).sum())
    return {"1X": home + draw, "12": home + away, "X2": draw + away}


def to_advance(lam: float, mu: float, *, et_fraction: float = 1.0 / 3.0) -> tuple[float, float]:
    """(P(home advances), P(away advances)) in a single knockout match.

    Regulation draw -> extra time (goal rates scaled by `et_fraction`, ~30/90 min); a still-level
    ET -> penalties, modelled as 50/50. This is the "to qualify" market, distinct from 1X2.
    """
    reg = score_matrix(lam, mu)
    reg_home = float(np.tril(reg, -1).sum())
    reg_draw = float(np.trace(reg))

    et = score_matrix(lam * et_fraction, mu * et_fraction)
    et_home = float(np.tril(et, -1).sum())
    et_draw = float(np.trace(et))

    p_home_adv = reg_home + reg_draw * (et_home + et_draw * 0.5)
    return p_home_adv, 1.0 - p_home_adv
