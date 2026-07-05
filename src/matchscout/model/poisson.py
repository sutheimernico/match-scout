"""Independent-Poisson scoreline model -> market probabilities.

The base goal model: given expected home/away goals (`lambda_home`, `mu_away`) it builds
the score-probability matrix under independent Poisson margins and reads off the 1X2 and
Over/Under-2.5 market probabilities. This is the rho=0 / no-time-decay ablation baseline
(council D9); Dixon-Coles adds the low-score tau correction + time-decay on top of it.
"""

from __future__ import annotations

from math import factorial

import numpy as np

from matchscout.data.schema import Market, Selection

MAX_GOALS = 10


def _poisson_pmf(rate: float, max_goals: int) -> np.ndarray:
    """P(k goals) for k in 0..max_goals under Poisson(rate)."""
    k = np.arange(max_goals + 1)
    fact = np.array([factorial(int(x)) for x in k], dtype=float)
    return np.exp(-rate) * rate**k / fact


def score_matrix(lambda_home: float, mu_away: float, max_goals: int = MAX_GOALS) -> np.ndarray:
    """Score-probability matrix `m[i, j]` = P(home scores i, away scores j).

    Independent Poisson margins; renormalized so the truncated tail does not lose mass.
    """
    if lambda_home <= 0 or mu_away <= 0:
        raise ValueError("expected goals must be positive")
    home = _poisson_pmf(lambda_home, max_goals)
    away = _poisson_pmf(mu_away, max_goals)
    matrix = np.outer(home, away)
    return matrix / matrix.sum()


def most_likely_score(matrix: np.ndarray) -> tuple[int, int]:
    """The (home_goals, away_goals) cell with the highest probability."""
    i, j = np.unravel_index(int(np.argmax(matrix)), matrix.shape)
    return int(i), int(j)


def market_probs(matrix: np.ndarray) -> dict[str, dict[str, float]]:
    """Read 1X2 and Over/Under-2.5 probabilities off a score matrix."""
    home_win = float(np.tril(matrix, -1).sum())  # i > j (home scores more)
    draw = float(np.trace(matrix))
    away_win = float(np.triu(matrix, 1).sum())  # i < j

    idx = np.arange(matrix.shape[0])
    totals = np.add.outer(idx, idx)
    over = float(matrix[totals >= 3].sum())
    under = float(matrix[totals <= 2].sum())

    return {
        Market.ONE_X_TWO.value: {
            Selection.HOME.value: home_win,
            Selection.DRAW.value: draw,
            Selection.AWAY.value: away_win,
        },
        Market.OVER_UNDER_25.value: {
            Selection.OVER.value: over,
            Selection.UNDER.value: under,
        },
    }
