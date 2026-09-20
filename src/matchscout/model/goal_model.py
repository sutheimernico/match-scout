"""Fittable Poisson / Dixon-Coles team-strength goal model.

Each team gets an attack and a defence (defensive-strength) parameter; a global home
advantage and base rate complete the model:

    log lambda_home = base + home_adv + attack[home] - defence[away]
    log mu_away     = base          + attack[away] - defence[home]

`fit_poisson` is the rho=0 / no-time-decay ablation baseline (council D9). `fit_dixon_coles`
adds the Dixon-Coles tau low-score correction (fitted rho) and exponential time-decay
(older matches down-weighted by a half-life). Both fit by maximum likelihood on the PLAYED
matches the caller passes. A small ridge penalty resolves attack/defence identifiability and
doubles as promoted-team shrinkage toward the league mean (D9).

No-lookahead is enforced here, not trusted: `fit_dixon_coles` requires an `as_of` date and
raises `LookaheadError` if any training match is dated on or after it. Caller discipline used
to be the only guard (`walk_forward.py`'s `< day` filter); now every future caller — the
forward paper loop included — inherits the protection by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from matchscout.model.poisson import market_probs, score_matrix


class LookaheadError(ValueError):
    """Raised when a fit would train on a match dated on or after its prediction date."""


def _align(dates: pd.Series, as_of) -> tuple[pd.Series, pd.Timestamp]:
    """Put a date column and a reference timestamp on the same timezone footing.

    Sources differ (football-data.co.uk is tz-naive local, football-data.org is tz-aware UTC),
    and a naive-vs-aware comparison raises instead of answering — which would turn the guard
    below into a crash rather than a check.
    """
    dates = pd.to_datetime(dates)
    ref = pd.Timestamp(as_of)
    tz = dates.dt.tz
    if tz is None:
        ref = ref.tz_convert("UTC").tz_localize(None) if ref.tz is not None else ref
    else:
        ref = ref.tz_localize(tz) if ref.tz is None else ref.tz_convert(tz)
    return dates, ref


def _assert_no_lookahead(played: pd.DataFrame, as_of) -> None:
    """Hard-fail if the training frame reaches into (or onto) the prediction day."""
    if "date" not in played.columns:
        raise LookaheadError(
            "fit: as_of was given but the training frame has no `date` column — "
            "an undated frame cannot be proven free of lookahead."
        )
    dates, ref = _align(played["date"], as_of)
    offenders = int((dates >= ref).sum())
    if offenders:
        raise LookaheadError(
            f"fit: {offenders} training match(es) dated on or after as_of={ref} "
            f"(latest {dates.max()}) — a model may never see its own prediction day."
        )


@dataclass(frozen=True)
class GoalModel:
    teams: tuple[str, ...]
    attack: dict[str, float]
    defence: dict[str, float]
    home_adv: float
    base: float
    rho: float = 0.0  # Dixon-Coles low-score correction; 0.0 => plain independent Poisson

    def rates(self, home: str, away: str) -> tuple[float, float]:
        """Expected (home_goals, away_goals) for a fixture."""
        for team in (home, away):
            if team not in self.attack:
                raise KeyError(f"unknown team {team!r}; model was not fit on it")
        log_home = self.base + self.home_adv + self.attack[home] - self.defence[away]
        log_away = self.base + self.attack[away] - self.defence[home]
        return float(np.exp(log_home)), float(np.exp(log_away))

    def score_matrix(self, home: str, away: str) -> np.ndarray:
        """The (tau-corrected) score-probability matrix for a fixture."""
        lam, mu = self.rates(home, away)
        matrix = score_matrix(lam, mu)
        if self.rho:
            matrix = _apply_tau(matrix, lam, mu, self.rho)
        return matrix

    def predict(self, home: str, away: str) -> dict[str, dict[str, float]]:
        """1X2 + Over/Under-2.5 market probabilities for a fixture."""
        return market_probs(self.score_matrix(home, away))


def _apply_tau(matrix: np.ndarray, lam: float, mu: float, rho: float) -> np.ndarray:
    """Dixon-Coles low-score correction on the four (0/1, 0/1) cells; renormalized (D9)."""
    m = matrix.copy()
    m[0, 0] *= 1 - lam * mu * rho
    m[0, 1] *= 1 + lam * rho
    m[1, 0] *= 1 + mu * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def _tau_vec(
    x: np.ndarray, y: np.ndarray, lam: np.ndarray, mu: np.ndarray, rho: float
) -> np.ndarray:
    """Per-match tau factor for the likelihood (1.0 outside the four low-score cells)."""
    t = np.ones_like(lam)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    t[m00] = 1 - lam[m00] * mu[m00] * rho
    t[m01] = 1 + lam[m01] * rho
    t[m10] = 1 + mu[m10] * rho
    t[m11] = 1 - rho
    return t


def _fit(
    matches: pd.DataFrame,
    *,
    fit_rho: bool,
    ridge: float,
    half_life_days: float | None = None,
    as_of: pd.Timestamp | None = None,
) -> GoalModel:
    played = matches[matches["status"] == "played"]
    if played.empty:
        raise ValueError("fit: no played matches to fit on")
    if as_of is not None:
        _assert_no_lookahead(played, as_of)

    teams = sorted(set(played["home"]) | set(played["away"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    hi = played["home"].map(idx).to_numpy()
    ai = played["away"].map(idx).to_numpy()
    hg = played["ft_home_goals"].astype(float).to_numpy()
    ag = played["ft_away_goals"].astype(float).to_numpy()

    if half_life_days is not None:
        dates = pd.to_datetime(played["date"])
        dates, ref = _align(dates, as_of) if as_of is not None else (dates, dates.max())
        age = (ref - dates).dt.days.clip(lower=0).to_numpy()
        weights = np.exp(-np.log(2) / half_life_days * age)
    else:
        weights = np.ones(len(hi))

    def neg_log_lik(theta: np.ndarray) -> float:
        attack = theta[:n]
        defence = theta[n : 2 * n]
        home_adv = theta[2 * n]
        base = theta[2 * n + 1]
        rho = theta[2 * n + 2] if fit_rho else 0.0
        log_home = base + home_adv + attack[hi] - defence[ai]
        log_away = base + attack[ai] - defence[hi]
        lam = np.exp(log_home)
        mu = np.exp(log_away)
        term = lam - hg * log_home + mu - ag * log_away
        if fit_rho:
            tau = _tau_vec(hg, ag, lam, mu, rho)
            term = term - np.log(np.clip(tau, 1e-9, None))
        nll = float(np.sum(weights * term))
        return nll + ridge * float(attack @ attack + defence @ defence)

    size = 2 * n + 2 + (1 if fit_rho else 0)
    x0 = np.zeros(size)
    x0[2 * n] = 0.25  # home advantage prior
    x0[2 * n + 1] = np.log(1.35)  # base scoring-rate prior
    bounds = None
    if fit_rho:
        bounds = [(None, None)] * (2 * n + 2) + [(-0.2, 0.2)]  # keep tau > 0
    res = minimize(neg_log_lik, x0, method="L-BFGS-B", bounds=bounds)

    theta = res.x
    return GoalModel(
        teams=tuple(teams),
        attack={t: float(theta[idx[t]]) for t in teams},
        defence={t: float(theta[n + idx[t]]) for t in teams},
        home_adv=float(theta[2 * n]),
        base=float(theta[2 * n + 1]),
        rho=float(theta[2 * n + 2]) if fit_rho else 0.0,
    )


def fit_poisson(
    matches: pd.DataFrame, *, ridge: float = 0.01, as_of: pd.Timestamp | None = None
) -> GoalModel:
    """Fit the rho=0 / no-time-decay Poisson ablation baseline.

    `as_of` is optional here because this baseline is an offline ablation that never prices a
    bet; when given it is enforced exactly as in `fit_dixon_coles`.
    """
    return _fit(matches, fit_rho=False, ridge=ridge, as_of=as_of)


def fit_dixon_coles(
    matches: pd.DataFrame,
    *,
    as_of: pd.Timestamp,
    ridge: float = 0.01,
    half_life_days: float | None = None,
) -> GoalModel:
    """Fit the full Dixon-Coles model: fitted low-score rho + optional exponential time-decay.

    `as_of` is REQUIRED and is both the decay reference and the no-lookahead boundary: every
    training match must be dated strictly before it, or the fit raises `LookaheadError`.
    `half_life_days` sets the decay (older matches down-weighted); None disables it.
    """
    return _fit(
        matches, fit_rho=True, ridge=ridge, half_life_days=half_life_days, as_of=as_of
    )
