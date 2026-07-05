import pandas as pd

from matchscout.backtest.placebo import placebo_test

_EMPTY_ODDS = pd.DataFrame(
    columns=["match_id", "market", "selection", "book", "odds", "is_closing"]
)


def _matches():
    # 10 home wins + 10 away wins
    rows = []
    day = pd.Timestamp("2024-01-01")
    for i in range(20):
        home_win = i < 10
        rows.append(
            (f"m{i}", "played", day, "H" + str(i), "A" + str(i),
             2 if home_win else 0, 0 if home_win else 2)
        )
        day += pd.Timedelta(days=2)
    return pd.DataFrame(
        rows,
        columns=["match_id", "status", "date", "home", "away", "ft_home_goals", "ft_away_goals"],
    )


def _winning_picks(matches):
    # bet the ACTUAL winner of each match at even odds -> a guaranteed-win "leak"
    picks = []
    for r in matches.itertuples():
        sel = "H" if r.ft_home_goals > r.ft_away_goals else "A"
        picks.append((r.match_id, "1x2", sel, 0.5, 2.0))
    return pd.DataFrame(picks, columns=["match_id", "market", "selection", "p_model", "odds"])


def test_leak_is_detected():
    matches = _matches()
    result = placebo_test(_winning_picks(matches), matches, _EMPTY_ODDS, n=30, seed=1)
    # a guaranteed-win selection yields +1.0 real vs ~0 under permutation -> clearly exceeds
    assert result["real_yield"] == 1.0
    assert result["real_exceeds_placebo_95pct"] is True
    assert result["placebo_mean_yield"] < result["real_yield"]


def test_structure_and_determinism():
    matches = _matches()
    picks = _winning_picks(matches)
    a = placebo_test(picks, matches, _EMPTY_ODDS, n=10, seed=7)
    b = placebo_test(picks, matches, _EMPTY_ODDS, n=10, seed=7)
    assert a == b
    assert a["n_permutations"] == 10
