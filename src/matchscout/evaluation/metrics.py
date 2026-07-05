"""Probabilistic scoring + calibration metrics.

These are the honesty-critical metrics (council D2/D9): a goal model is judged by how well
its probabilities are *calibrated* against outcomes and against the market, not by accuracy.
`brier_score` and `log_loss` are strictly proper scoring rules; `reliability_curve` bins
predicted vs. observed frequency for a single binary event (e.g. P(home win), P(over 2.5)).
"""

from __future__ import annotations

import numpy as np


def brier_score(probs: np.ndarray, y_true: np.ndarray) -> float:
    """Multiclass Brier score: mean squared error between predicted probs and one-hot outcome.

    `probs` is (n, k); `y_true` is (n,) integer class indices. Lower is better; 0 = perfect.
    """
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y_true, dtype=int)
    n, k = probs.shape
    onehot = np.zeros((n, k))
    onehot[np.arange(n), y] = 1.0
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def log_loss(probs: np.ndarray, y_true: np.ndarray, eps: float = 1e-15) -> float:
    """Multiclass log-loss (cross-entropy). Lower is better; 0 = perfect certainty."""
    probs = np.clip(np.asarray(probs, dtype=float), eps, 1.0)
    y = np.asarray(y_true, dtype=int)
    n = len(y)
    p_true = probs[np.arange(n), y]
    return float(-np.mean(np.log(p_true)))


def reliability_curve(
    prob: np.ndarray, y: np.ndarray, n_bins: int = 10
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reliability (calibration) curve for a single binary event.

    `prob` is (n,) predicted P(event); `y` is (n,) realized 0/1. Returns, for each non-empty
    equal-width bin: (mean predicted prob, observed frequency, count). A well-calibrated model
    has mean-predicted ~= observed in every bin.
    """
    prob = np.asarray(prob, dtype=float)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(prob, edges[1:-1]), 0, n_bins - 1)
    pred, obs, cnt = [], [], []
    for b in range(n_bins):
        mask = idx == b
        c = int(mask.sum())
        if c == 0:
            continue
        pred.append(float(prob[mask].mean()))
        obs.append(float(y[mask].mean()))
        cnt.append(c)
    return np.array(pred), np.array(obs), np.array(cnt)
