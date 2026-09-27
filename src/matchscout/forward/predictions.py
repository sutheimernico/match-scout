"""Append-only log of every forward prediction — including the fixtures the loop did not bet.

Paper stakes only — this is a record of probabilities, nothing here places a bet.

The bet ledger is the selected tail of the forward record: a handful of fixtures per matchday
where the model disagreed with the price by more than the threshold. That is a small, noisy
sample and a biased one (selection on disagreement). The prediction log is all of it: every
fixture the model priced, with the market's own de-vigged view next to it. Model-vs-market
calibration on every fixture is the larger, unselected sample — and the honest first test of
whether the bets can mean anything.

Same storage discipline as `ledger.py`: an event log in `data/predictions.jsonl`.

- one `predicted` line per `match_id`, at first (priced) sight — **first write wins**. The
  model is refitted every run; a later, better-informed forecast for the same fixture must not
  replace the one that was on record first, or the log would drift towards hindsight.
- one `settled` line when the result is known, merged onto the prediction.

Fields (`PREDICTION_COLUMNS`): identity (`match_id`, `competition`, `date`, `kickoff` as the
source states it — UK local, no offset — `home`, `away`), model probabilities (`p_*`), the
pre-match prices at the selection book (`odds_*`, null if the feed had none) and their Shin
de-vigged implied probabilities (`mkt_*`), provenance (`timestamp_known`, `run_id`, `trial_id`),
and at settlement `ft_home_goals`, `ft_away_goals`, `result` (H/D/A), `settled_at`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from matchscout.forward.ledger import _append_jsonl, _read_jsonl

DEFAULT_PREDICTIONS = Path("data/predictions.jsonl")

PREDICTED = "predicted"
SETTLED = "settled"

PREDICTION_COLUMNS = [
    "match_id",
    "competition",
    "date",
    "kickoff",
    "home",
    "away",
    "p_H",
    "p_D",
    "p_A",
    "p_over",
    "p_under",
    "book",
    "odds_H",
    "odds_D",
    "odds_A",
    "odds_over",
    "odds_under",
    "mkt_H",
    "mkt_D",
    "mkt_A",
    "mkt_over",
    "mkt_under",
    "timestamp_known",
    "run_id",
    "trial_id",
    "status",
    "ft_home_goals",
    "ft_away_goals",
    "result",
    "settled_at",
]


def load_prediction_events(path: Path | str = DEFAULT_PREDICTIONS) -> list[dict[str, Any]]:
    return _read_jsonl(path)


def current_predictions(path: Path | str = DEFAULT_PREDICTIONS) -> pd.DataFrame:
    """Fold the event log to one row per fixture (its latest state)."""
    state: dict[str, dict[str, Any]] = {}
    for event in load_prediction_events(path):
        state[event["match_id"]] = event
    if not state:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in PREDICTION_COLUMNS})
    return pd.DataFrame(list(state.values()), columns=PREDICTION_COLUMNS)


def _priced(row: dict[str, Any]) -> bool:
    return row.get("odds_H") is not None


def record_predictions(
    path: Path | str, rows: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Append predictions for fixtures not on record yet; return the ones actually written.

    One exception to first-write-wins: a record made while the feed had no price is superseded
    once, by the first priced sighting — otherwise that fixture could never be compared with
    the market. Both lines stay in the log; the later one is still pre-kickoff by construction.
    """
    known = {e["match_id"]: _priced(e) for e in load_prediction_events(path)}
    fresh: list[dict[str, Any]] = []
    for row in rows:
        mid = row["match_id"]
        if mid in known and (known[mid] or not _priced(row)):
            continue
        known[mid] = _priced(row)
        fresh.append({column: row.get(column) for column in PREDICTION_COLUMNS})
    _append_jsonl(path, fresh)
    return fresh


def settle_predictions(
    path: Path | str,
    scores: dict[str, tuple[int, int]],
    *,
    settled_at: str,
) -> list[dict[str, Any]]:
    """Append a settlement for every open prediction whose fixture now has a score."""
    state = {event["match_id"]: event for event in load_prediction_events(path)}
    written: list[dict[str, Any]] = []
    for mid, previous in state.items():
        if previous.get("status") != PREDICTED or mid not in scores:
            continue
        hg, ag = scores[mid]
        merged = {
            **previous,
            "status": SETTLED,
            "ft_home_goals": int(hg),
            "ft_away_goals": int(ag),
            "result": "H" if hg > ag else ("A" if hg < ag else "D"),
            "settled_at": settled_at,
        }
        written.append({column: merged.get(column) for column in PREDICTION_COLUMNS})
    _append_jsonl(path, written)
    return written
