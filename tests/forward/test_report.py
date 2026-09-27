"""Forward record numbers: all three states, n everywhere, no verdict from a tiny sample."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from matchscout.forward.ledger import BET_COLUMNS
from matchscout.forward.predictions import PREDICTION_COLUMNS
from matchscout.forward.report import forward_record


def _bets(rows):
    return pd.DataFrame(rows, columns=BET_COLUMNS)


def _bet(i, status="settled", won=False, odds=2.0, clv=-0.05):
    return {
        "bet_id": f"m{i}|1x2|H",
        "match_id": f"m{i}",
        "date": f"2026-10-{10 + i % 5:02d}",
        "market": "1x2",
        "selection": "H",
        "odds_taken": odds,
        "stake": 10.0,
        "timestamp_known": "2026-10-08T06:47:00+00:00",
        "status": status,
        "won": won if status == "settled" else None,
        "pnl": (10.0 * (odds - 1) if won else -10.0) if status == "settled" else None,
        "clv_book": "Avg" if status == "settled" else None,
        "clv": clv if status == "settled" else None,
    }


def _pred(i, result, model, market):
    return {
        "match_id": f"m{i}",
        "p_H": model[0],
        "p_D": model[1],
        "p_A": model[2],
        "mkt_H": market[0],
        "mkt_D": market[1],
        "mkt_A": market[2],
        "timestamp_known": "2026-10-08T06:47:00+00:00",
        "status": "settled",
        "result": result,
    }


def test_empty_ledgers_give_the_empty_state_and_valid_json():
    record = forward_record(_bets([]), pd.DataFrame(columns=PREDICTION_COLUMNS))
    assert record["state"] == "empty"
    assert record["bets"]["n_bets"] == 0
    json.dumps(record, allow_nan=False)  # a browser must be able to parse it


def test_pending_only_is_the_pending_state():
    record = forward_record(
        _bets([_bet(1, status="pending")]), pd.DataFrame(columns=PREDICTION_COLUMNS)
    )
    assert record["state"] == "pending"
    assert record["bets"]["n_pending"] == 1
    assert record["since"] == "2026-10-08"


def test_settled_bets_report_yield_ci_clv_book_and_withhold_a_verdict_below_30():
    bets = _bets([_bet(i, won=(i == 0), odds=3.0) for i in range(12)])
    record = forward_record(bets, pd.DataFrame(columns=PREDICTION_COLUMNS))
    b = record["bets"]
    assert record["state"] == "settled"
    assert b["n_bets"] == 12 and b["n_won"] == 1
    assert b["profit"] == pytest.approx(20.0 - 110.0)
    assert b["yield_ci"][0] <= b["yield"] <= b["yield_ci"][1]
    assert b["clv_books"] == {"Avg": 12}
    assert "Too few" in b["verdict"]
    assert b["curve"][-1]["profit"] == pytest.approx(-90.0)


def test_calibration_compares_model_and_market_brier_on_the_same_fixtures():
    preds = pd.DataFrame(
        [
            _pred(1, "H", (0.6, 0.2, 0.2), (0.5, 0.25, 0.25)),  # model sharper and right
            _pred(2, "A", (0.6, 0.2, 0.2), (0.5, 0.25, 0.25)),  # model sharper and wrong
        ],
        columns=PREDICTION_COLUMNS,
    )
    cal = forward_record(_bets([]), preds)["calibration"]
    # hand-computed: model (0.24, 1.04) -> 0.64; market (0.375, 0.875) -> 0.625
    assert cal["n"] == 2
    assert cal["brier_model"] == pytest.approx(0.64)
    assert cal["brier_market"] == pytest.approx(0.625)
    assert cal["brier_diff"] == pytest.approx(0.015)
    assert cal["hit_rate_model"] == cal["hit_rate_market"] == 0.5
    assert "Too few" in cal["verdict"]
