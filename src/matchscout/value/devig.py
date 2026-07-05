"""Convert bookmaker decimal odds into implied probabilities, removing the margin (vig).

Raw implied probabilities `1/odds` sum to more than 1 — the overround. De-vigging removes
it. Two methods (council D6): `devig_proportional` (simple normalization — has a documented
favourite-longshot bias) and `devig_shin` (Shin's insider-trading model, the default for the
closing-line benchmark, which corrects that bias by nudging probability mass from longshots
toward favourites).

De-vig is used ONLY to build the market benchmark / calibration comparison — never as a
betting-selection input. Selection uses the raw EV edge on the with-vig odds (see edge.py).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def booksum(odds: np.ndarray) -> float:
    """Sum of raw implied probabilities (`> 1`); `booksum - 1` is the overround."""
    return float(np.sum(1.0 / np.asarray(odds, dtype=float)))


def devig_proportional(odds: np.ndarray) -> np.ndarray:
    """Remove the margin by normalizing raw implied probabilities to sum to 1."""
    raw = 1.0 / np.asarray(odds, dtype=float)
    return raw / raw.sum()


def devig_shin(odds: np.ndarray) -> np.ndarray:
    """Shin's method: solve for the insider proportion z so probabilities sum to 1.

    Falls back to proportional if no valid z is bracketed (e.g. a near-zero overround).
    """
    pi = 1.0 / np.asarray(odds, dtype=float)
    book = pi.sum()

    def sum_p(z: float) -> np.ndarray:
        return (np.sqrt(z**2 + 4 * (1 - z) * pi**2 / book) - z) / (2 * (1 - z))

    def gap(z: float) -> float:
        return float(sum_p(z).sum() - 1.0)

    lo, hi = 1e-9, 1 - 1e-6
    if gap(lo) * gap(hi) > 0:  # no sign change -> cannot solve; use proportional
        return devig_proportional(odds)
    z = brentq(gap, lo, hi)
    p = sum_p(z)
    return p / p.sum()
