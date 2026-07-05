"""Purged + embargoed walk-forward splits for the ML challenger (council D1).

Time-ordered expanding-window cross-validation: each test block sits strictly after its training
window, with an `embargo` gap of samples dropped from the end of training before each test block.
For point-event match labels (no overlapping horizons) the embargo is what stands in for López de
Prado purging — it prevents very-recent form from leaking across the train/test boundary. Indices
are assumed sorted by date by the caller.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np


def purged_walk_forward_splits(
    n_samples: int, *, n_splits: int = 5, embargo: int = 0
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, test_idx) for expanding-window walk-forward with an embargo gap.

    The data is divided into `n_splits + 1` contiguous blocks; block k (k>=1) is a test set whose
    training set is everything before it minus the last `embargo` samples. Train and test never
    overlap and train always precedes test in time.
    """
    if n_splits < 1:
        raise ValueError("n_splits must be >= 1")
    fold = n_samples // (n_splits + 1)
    if fold == 0:
        raise ValueError(f"too few samples ({n_samples}) for {n_splits} splits")

    for k in range(1, n_splits + 1):
        test_start = k * fold
        test_end = (k + 1) * fold if k < n_splits else n_samples
        train_end = max(0, test_start - embargo)
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(test_start, test_end)
        if len(train_idx) and len(test_idx):
            yield train_idx, test_idx
