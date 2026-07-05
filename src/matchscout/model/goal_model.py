"""Fittable Poisson team-strength goal model (Dixon-Coles base, rho=0 / no time-decay).

Each team gets an attack and a defence (defensive-strength) parameter; a global home
advantage and base rate complete the model:

    log lambda_home = base + home_adv + attack[home] - defence[away]
    log mu_away     = base          + attack[away] - defence[home]

Fit by maximum likelihood (independent Poisson) on a set of PLAYED matches — the caller
passes only matches before the prediction matchday, so there is no lookahead. A small
ridge penalty resolves the attack/defence identifiability and doubles as the promoted-team
shrinkage-toward-league-mean that the council asked for (D9). The tau low-score correction
and exponential time-decay are added in later iterations.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from matchscout.model.poisson import market_probs, score_matrix


@dataclass(frozen=True)
class GoalModel:
    teams: tuple[str, ...]
    attack: dict[str, float]
    defence: dict[str, float]
    home_adv: float
    base: float

    def rates(self, home: str, away: str) -> tuple[float, float]:
        """Expected (home_goals, away_goals) for a fixture."""
        for team in (home, away):
            if team not in self.attack:
                raise KeyError(f"unknown team {team!r}; model was not fit on it")
        log_home = self.base + self.home_adv + self.attack[home] - self.defence[away]
        log_away = self.base + self.attack[away] - self.defence[home]
        return float(np.exp(log_home)), float(np.exp(log_away))

    def predict(self, home: str, away: str) -> dict[str, dict[str, float]]:
        """1X2 + Over/Under-2.5 market probabilities for a fixture."""
        lam, mu = self.rates(home, away)
        return market_probs(score_matrix(lam, mu))


def fit_poisson(matches: pd.DataFrame, *, ridge: float = 0.01) -> GoalModel:
    """Fit the Poisson goal model by MLE on the PLAYED matches in `matches`.

    Deterministic: zero-initialized, L-BFGS-B. `matches` must already be restricted to
    the information window the caller is allowed to use (no lookahead is enforced here).
    """
    played = matches[matches["status"] == "played"]
    if played.empty:
        raise ValueError("fit_poisson: no played matches to fit on")

    teams = sorted(set(played["home"]) | set(played["away"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    hi = played["home"].map(idx).to_numpy()
    ai = played["away"].map(idx).to_numpy()
    hg = played["ft_home_goals"].astype(float).to_numpy()
    ag = played["ft_away_goals"].astype(float).to_numpy()

    def neg_log_lik(theta: np.ndarray) -> float:
        attack = theta[:n]
        defence = theta[n : 2 * n]
        home_adv = theta[2 * n]
        base = theta[2 * n + 1]
        log_home = base + home_adv + attack[hi] - defence[ai]
        log_away = base + attack[ai] - defence[hi]
        lam = np.exp(log_home)
        mu = np.exp(log_away)
        nll = np.sum(lam - hg * log_home + mu - ag * log_away)
        nll += ridge * (attack @ attack + defence @ defence)
        return float(nll)

    x0 = np.zeros(2 * n + 2)
    x0[2 * n] = 0.25  # home advantage prior
    x0[2 * n + 1] = np.log(1.35)  # base scoring-rate prior
    res = minimize(neg_log_lik, x0, method="L-BFGS-B")

    theta = res.x
    return GoalModel(
        teams=tuple(teams),
        attack={t: float(theta[idx[t]]) for t in teams},
        defence={t: float(theta[n + idx[t]]) for t in teams},
        home_adv=float(theta[2 * n]),
        base=float(theta[2 * n + 1]),
    )
