"""Shadow-mode fixture tips (no odds): fit the goal model on played history, predict upcoming.

For competitions without free odds — Champions League, World Cup — the model produces the full
goals-only market board (1X2, all Over/Under lines, BTTS, correct score, and the knockout
"to advance" market) but never a stake or P&L. This is SHADOW-MODE: honestly-labelled predictions.
Player markets (goalscorers) and event markets (corners/cards) are NOT here — the free data has no
player/event dimension. Teams with no training history are skipped rather than guessed.
"""

from __future__ import annotations

import pandas as pd

from matchscout.model.goal_model import fit_dixon_coles
from matchscout.model.markets import all_over_under, btts, correct_score, to_advance
from matchscout.model.poisson import market_probs, most_likely_score

TIP_COLUMNS = [
    "match_id", "date", "home", "away",
    "p_H", "p_D", "p_A",
    "p_over05", "p_over15", "p_over25", "p_over35",
    "p_btts", "p_home_adv", "p_away_adv",
    "tip_1x2", "most_likely_score", "top_scores",
]


def fixture_tips(
    train_matches: pd.DataFrame,
    fixtures: pd.DataFrame,
    *,
    as_of: pd.Timestamp,
    half_life_days: float | None = 365.0,
) -> pd.DataFrame:
    """Fit Dixon-Coles on played `train_matches`; return the goals-market board per fixture.

    `as_of` is required: it is the moment the tips are made, and the fit rejects any training
    match dated on or after it (`LookaheadError`).
    """
    model = fit_dixon_coles(train_matches, half_life_days=half_life_days, as_of=as_of)
    teams = set(model.teams)

    rows = []
    for fixture in fixtures.itertuples():
        if fixture.home not in teams or fixture.away not in teams:
            continue
        matrix = model.score_matrix(fixture.home, fixture.away)
        one_x_two = market_probs(matrix)["1x2"]
        ou = all_over_under(matrix)
        p_btts, _ = btts(matrix)
        lam, mu = model.rates(fixture.home, fixture.away)
        adv_home, adv_away = to_advance(lam, mu)
        home_goals, away_goals = most_likely_score(matrix)
        top = correct_score(matrix, top_n=3)
        rows.append(
            {
                "match_id": fixture.match_id,
                "date": fixture.date,
                "home": fixture.home,
                "away": fixture.away,
                "p_H": one_x_two["H"],
                "p_D": one_x_two["D"],
                "p_A": one_x_two["A"],
                "p_over05": ou[0.5],
                "p_over15": ou[1.5],
                "p_over25": ou[2.5],
                "p_over35": ou[3.5],
                "p_btts": p_btts,
                "p_home_adv": adv_home,
                "p_away_adv": adv_away,
                "tip_1x2": max(one_x_two, key=one_x_two.get),
                "most_likely_score": f"{home_goals}-{away_goals}",
                "top_scores": "; ".join(f"{s} {p:.0%}" for s, p in top),
            }
        )
    if not rows:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in TIP_COLUMNS})
    return pd.DataFrame(rows)


def suggest_combo(tips: pd.DataFrame, *, n_legs: int = 3) -> dict:
    """A combo (accumulator) of the highest-confidence 1X2 legs.

    Shadow-mode: only the combined model probability is shown, never a payout. Accumulators
    compound the bookmaker margin and are −EV — this is an illustration, not advice.
    """
    if tips.empty:
        return {"legs": [], "combined_prob": float("nan"), "n_legs": 0}
    ranked = tips.copy()
    ranked["conf"] = ranked[["p_H", "p_D", "p_A"]].max(axis=1)
    top = ranked.nlargest(n_legs, "conf")
    legs = [
        {"match": f"{r.home} vs {r.away}", "pick": r.tip_1x2, "p": float(r.conf)}
        for r in top.itertuples()
    ]
    combined = float(top["conf"].prod())
    return {"legs": legs, "combined_prob": combined, "n_legs": len(legs)}
