import math

import pandas as pd

from matchscout.backtest.engine import LEDGER_COLUMNS, settle_bets


def _matches():
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "status": ["played", "played"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-08"]),
            "home": ["A", "C"],
            "away": ["B", "D"],
            "ft_home_goals": [2, 0],  # m1 -> H (and over 2.5); m2 -> D (under)
            "ft_away_goals": [1, 0],
        }
    )


def _picks():
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "market": ["1x2", "1x2"],
            "selection": ["H", "H"],  # m1 H wins, m2 H loses (actual D)
            "p_model": [0.55, 0.40],
            "odds": [2.0, 3.0],
        }
    )


def _closing_odds():
    # Pinnacle closing 1X2 for m1 only (m2 has none -> CLV NaN there)
    rows = []
    for sel, price in zip(["H", "D", "A"], [2.0, 3.4, 3.6], strict=True):
        rows.append(("m1", "1x2", sel, "PS", price, True))
    return pd.DataFrame(
        rows, columns=["match_id", "market", "selection", "book", "odds", "is_closing"]
    )


def test_flat_settlement_math():
    ledger = settle_bets(_picks(), _matches(), _closing_odds(), staking="flat", flat_unit=10.0)
    assert list(ledger["won"]) == [True, False]
    assert list(ledger["pnl"]) == [10.0, -10.0]  # 10*(2-1) win; -10 loss
    assert list(ledger["bankroll_after"]) == [1010.0, 1000.0]


def test_clv_present_and_absent():
    ledger = settle_bets(_picks(), _matches(), _closing_odds())
    by_match = ledger.set_index("match_id")
    assert math.isfinite(by_match.loc["m1", "clv"])  # closing available
    assert math.isnan(by_match.loc["m2", "clv"])  # no closing for m2


def test_kelly_stakes_positive_and_vary():
    ledger = settle_bets(
        _picks(), _matches(), _closing_odds(), staking="kelly", start_bankroll=1000.0
    )
    # m1 has +edge (0.55*2-1=0.10) -> positive stake; m2 -edge (0.4*3-1=0.20>0 actually)
    assert (ledger["stake"] > 0).all()


def test_empty_picks_returns_empty_ledger():
    empty = pd.DataFrame(columns=["match_id", "market", "selection", "p_model", "odds"])
    ledger = settle_bets(empty, _matches(), _closing_odds())
    assert ledger.empty
    assert list(ledger.columns) == LEDGER_COLUMNS


def test_chronological_order():
    # picks given out of order still settle by date
    picks = _picks().iloc[::-1].reset_index(drop=True)
    ledger = settle_bets(picks, _matches(), _closing_odds(), staking="flat", flat_unit=10.0)
    assert list(ledger["match_id"]) == ["m1", "m2"]
