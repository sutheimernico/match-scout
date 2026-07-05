import pandas as pd

from matchscout.backtest.placebo import market_null_test


def _matches():
    rows = []
    day = pd.Timestamp("2024-01-01")
    for i in range(20):
        home_win = i < 10
        rows.append(
            (f"m{i}", "played", day, f"H{i}", f"A{i}",
             2 if home_win else 0, 0 if home_win else 2)
        )
        day += pd.Timedelta(days=2)
    return pd.DataFrame(
        rows,
        columns=["match_id", "status", "date", "home", "away", "ft_home_goals", "ft_away_goals"],
    )


def _closing_odds(matches):
    # PS closing 1X2 = 3.0/3.0/3.0 -> de-vigged ~0.333 each (moderate market prob)
    rows = []
    for mid in matches["match_id"]:
        for sel in ("H", "D", "A"):
            rows.append((mid, "1x2", sel, "PS", 3.0, True))
    return pd.DataFrame(
        rows, columns=["match_id", "market", "selection", "book", "odds", "is_closing"]
    )


def _winning_picks(matches):
    picks = []
    for r in matches.itertuples():
        sel = "H" if r.ft_home_goals > r.ft_away_goals else "A"
        picks.append((r.match_id, "1x2", sel, 0.5, 2.0))
    return pd.DataFrame(picks, columns=["match_id", "market", "selection", "p_model", "odds"])


def test_leak_exceeds_market_null():
    m = _matches()
    result = market_null_test(_winning_picks(m), m, _closing_odds(m), n=500, seed=1)
    # guaranteed-win picks -> real yield +1.0; market null (p~0.333, odds 2.0) centers near -0.33
    assert result["real_yield"] == 1.0
    assert result["null_mean_yield"] < 0.0
    assert result["real_exceeds_null_95pct"] is True
    assert result["n_bets"] == 20


def test_no_closing_data_returns_empty():
    m = _matches()
    empty_odds = pd.DataFrame(
        columns=["match_id", "market", "selection", "book", "odds", "is_closing"]
    )
    result = market_null_test(_winning_picks(m), m, empty_odds, n=50)
    assert result["n_bets"] == 0
    assert result["real_exceeds_null_95pct"] is False


def test_deterministic():
    m = _matches()
    picks = _winning_picks(m)
    a = market_null_test(picks, m, _closing_odds(m), n=100, seed=7)
    b = market_null_test(picks, m, _closing_odds(m), n=100, seed=7)
    assert a == b
