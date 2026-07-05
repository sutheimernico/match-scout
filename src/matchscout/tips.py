"""Shadow-mode fixture tips (no odds): fit the goal model on played history, predict upcoming.

For competitions without free odds — Champions League, World Cup — the model can still produce
predictions (1X2 + Over/Under-2.5 probabilities, a pick, and the most-likely scoreline) but never
a stake or P&L. This is SHADOW-MODE: tips only, honestly labelled, no betting-slip simulation.
Teams with no training history (too few prior matches) are skipped rather than guessed.
"""

from __future__ import annotations

import pandas as pd

from matchscout.model.goal_model import fit_dixon_coles
from matchscout.model.poisson import most_likely_score, score_matrix

TIP_COLUMNS = [
    "match_id", "date", "home", "away",
    "p_H", "p_D", "p_A", "p_over", "p_under",
    "tip_1x2", "tip_ou", "most_likely_score",
]


def fixture_tips(
    train_matches: pd.DataFrame,
    fixtures: pd.DataFrame,
    *,
    half_life_days: float | None = 365.0,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Fit Dixon-Coles on played `train_matches`, return tips for each fixture with known teams."""
    model = fit_dixon_coles(train_matches, half_life_days=half_life_days, as_of=as_of)
    teams = set(model.teams)

    rows = []
    for fixture in fixtures.itertuples():
        if fixture.home not in teams or fixture.away not in teams:
            continue
        probs = model.predict(fixture.home, fixture.away)
        lam, mu = model.rates(fixture.home, fixture.away)
        home_goals, away_goals = most_likely_score(score_matrix(lam, mu))
        one_x_two, over_under = probs["1x2"], probs["ou25"]
        rows.append(
            {
                "match_id": fixture.match_id,
                "date": fixture.date,
                "home": fixture.home,
                "away": fixture.away,
                "p_H": one_x_two["H"],
                "p_D": one_x_two["D"],
                "p_A": one_x_two["A"],
                "p_over": over_under["over"],
                "p_under": over_under["under"],
                "tip_1x2": max(one_x_two, key=one_x_two.get),
                "tip_ou": "over" if over_under["over"] >= 0.5 else "under",
                "most_likely_score": f"{home_goals}-{away_goals}",
            }
        )
    if not rows:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in TIP_COLUMNS})
    return pd.DataFrame(rows)
