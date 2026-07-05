"""Leakage-safe walk-forward prediction over canonical matches.

For each matchday, the goal model is fit ONLY on played matches strictly before that day
(grouped by date, so same-day matches never train on each other), then used to predict that
day's fixtures. This is the point-in-time discipline of the whole harness (council D3): a
prediction for a past day is provably unaffected by future results. Matches whose teams have
no prior history (promoted sides) are skipped rather than predicted from nothing.
"""

from __future__ import annotations

import pandas as pd

from matchscout.model.goal_model import fit_dixon_coles


def _outcome_1x2(hg: int, ag: int) -> str:
    if hg > ag:
        return "H"
    return "A" if hg < ag else "D"


def _outcome_ou(hg: int, ag: int) -> str:
    return "over" if (hg + ag) >= 3 else "under"


def walk_forward_predict(
    matches: pd.DataFrame,
    *,
    min_train: int = 60,
    half_life_days: float | None = 180.0,
) -> pd.DataFrame:
    """Walk matchday-by-matchday, fitting on the past only; return predictions vs outcomes.

    Columns: match_id, competition, date, home, away, p_H/p_D/p_A, p_over/p_under,
    outcome_1x2, outcome_ou, n_train. `min_train` is the burn-in (minimum prior matches
    before predictions begin per competition).
    """
    played = matches[matches["status"] == "played"].copy()
    played["date"] = pd.to_datetime(played["date"])
    records: list[dict] = []

    for competition, comp_matches in played.groupby("competition"):
        comp_matches = comp_matches.sort_values("date")
        for day in sorted(comp_matches["date"].unique()):
            prior = comp_matches[comp_matches["date"] < day]
            if len(prior) < min_train:
                continue
            model = fit_dixon_coles(prior, half_life_days=half_life_days, as_of=day)
            teams = set(model.teams)
            for row in comp_matches[comp_matches["date"] == day].itertuples():
                if row.home not in teams or row.away not in teams:
                    continue
                probs = model.predict(row.home, row.away)
                hg, ag = int(row.ft_home_goals), int(row.ft_away_goals)
                records.append(
                    {
                        "match_id": row.match_id,
                        "competition": competition,
                        "date": day,
                        "home": row.home,
                        "away": row.away,
                        "p_H": probs["1x2"]["H"],
                        "p_D": probs["1x2"]["D"],
                        "p_A": probs["1x2"]["A"],
                        "p_over": probs["ou25"]["over"],
                        "p_under": probs["ou25"]["under"],
                        "outcome_1x2": _outcome_1x2(hg, ag),
                        "outcome_ou": _outcome_ou(hg, ag),
                        "n_train": len(prior),
                    }
                )
    return pd.DataFrame(records)
