"""Honest out-of-sample scorecard for the LightGBM 1X2 challenger.

Trains a multiclass GBDT over purged/embargoed walk-forward folds, accumulates strictly
out-of-sample probabilities, and scores them against Dixon-Coles and the market (closing line)
on the SAME rows. Per council D11: because the market-implied probability is a feature, beating
Dixon-Coles is nearly automatic and uninteresting — only beating the closing line is the real
test, and the expected honest outcome is that it does not.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from matchscout.evaluation.metrics import brier_score, log_loss
from matchscout.ml.dataset import build_1x2_dataset
from matchscout.ml.validation import purged_walk_forward_splits


def _fit_predict_oos(X: pd.DataFrame, y: np.ndarray, *, n_splits: int, embargo: int, seed: int,
                     n_estimators: int) -> np.ndarray:
    # Native Booster API (no scikit-learn dependency).
    params = {
        "objective": "multiclass", "num_class": 3, "learning_rate": 0.05,
        "num_leaves": 15, "min_child_samples": 5, "seed": seed,
        "deterministic": True, "force_row_wise": True, "num_threads": 1, "verbose": -1,
    }
    oos = np.full((len(y), 3), np.nan)
    for train, test in purged_walk_forward_splits(len(y), n_splits=n_splits, embargo=embargo):
        dtrain = lgb.Dataset(X.iloc[train], label=y[train])
        booster = lgb.train(params, dtrain, num_boost_round=n_estimators)
        oos[test] = booster.predict(X.iloc[test])
    return oos


def evaluate_challenger(
    preds: pd.DataFrame,
    odds: pd.DataFrame,
    *,
    n_splits: int = 5,
    embargo: int = 10,
    seed: int = 0,
    n_estimators: int = 200,
) -> dict:
    """OOS Brier + log-loss for the ML challenger vs. Dixon-Coles vs. the closing line."""
    X, y, _ = build_1x2_dataset(preds, odds)
    oos = _fit_predict_oos(
        X, y, n_splits=n_splits, embargo=embargo, seed=seed, n_estimators=n_estimators
    )
    mask = ~np.isnan(oos).any(axis=1)
    if not mask.any():
        raise ValueError("no out-of-sample rows produced; too few samples for the split")

    y_oos = y[mask]
    ml_p = oos[mask]
    dc_p = X.loc[mask, ["dc_H", "dc_D", "dc_A"]].to_numpy()
    mkt_p = X.loc[mask, ["mkt_H", "mkt_D", "mkt_A"]].to_numpy()

    report = {
        "n_oos": int(mask.sum()),
        "ml": {"brier": brier_score(ml_p, y_oos), "log_loss": log_loss(ml_p, y_oos)},
        "dixon_coles": {"brier": brier_score(dc_p, y_oos), "log_loss": log_loss(dc_p, y_oos)},
        "market": {"brier": brier_score(mkt_p, y_oos), "log_loss": log_loss(mkt_p, y_oos)},
    }
    report["beats_dixon_coles"] = bool(report["ml"]["log_loss"] < report["dixon_coles"]["log_loss"])
    report["beats_closing_line"] = bool(report["ml"]["log_loss"] < report["market"]["log_loss"])
    if report["beats_closing_line"]:
        report["verdict"] = (
            "ML beats the closing line out-of-sample — extraordinary for a free-data model; "
            "scrutinize hard for leakage before believing it."
        )
    elif report["beats_dixon_coles"]:
        report["verdict"] = (
            "ML beats Dixon-Coles (expected — it sees the market feature) but NOT the closing "
            "line: no real edge (the honest finding, council D11)."
        )
    else:
        report["verdict"] = "ML beats neither Dixon-Coles nor the closing line — no edge."
    return report
