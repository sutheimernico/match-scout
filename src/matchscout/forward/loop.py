"""The forward paper loop — the only part of this harness that cannot cheat.

Every historical result in this repo was computed after the fact. This loop is the answer to
"yes, but could you have known?": it decides before kickoff, records the decision with the price
it saw, and settles it against what actually happened. Nothing it writes can be re-derived with
hindsight, because the placement line is written before the result exists.

PAPER STAKES ONLY. The loop writes to a JSONL ledger. There is no broker, no account, no
execution path, and none is planned.

One run does five things, in this order:

1. **Fetch.** Played history + closing odds from the season CSVs (`MatchProvider`/`OddsProvider`),
   upcoming fixtures + pre-match prices from the fixtures feed (`FixtureProvider`). Verified
   2026-09-20: the current-season CSV contains played matches only, so the fixtures feed — not
   the season file — is what makes this work without an API key.
2. **Predict.** Dixon-Coles fit per competition on matches strictly before `now`
   (`as_of=now`, hard-guarded in the model layer), then predict the upcoming fixtures.
3. **Place.** Value bets at the frozen config's threshold, priced at the pre-match book, and
   only on fixtures still `min_lead_hours` away. A fixture the model predicts but cannot price
   is written as a `no_odds` row with stake 0 — visible, never an invented price.
4. **Settle.** Pending bets whose fixture has a result: won/lost at the price taken, CLV against
   the best available closing book. Pending bets whose fixture never showed up (postponed,
   renamed) are voided after `stale_after_days`.
5. **Snapshot.** One append-only bankroll row per run.

Idempotency is structural, not checked: the ledger refuses a known `bet_id` and refuses to settle
anything not pending, so re-running the loop any number of times a day changes nothing.

The config is frozen and logged as a trial (council D1) the first time it is used. Changing a
knob therefore costs a trial and raises the significance bar for everything — which is the point.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from matchscout.backtest.engine import closing_probs
from matchscout.backtest.metrics import summary, verdict
from matchscout.data.provider import FixtureProvider, HistoryProvider
from matchscout.data.schema import MATCH_COLUMNS, ODDS_COLUMNS, align_timestamps
from matchscout.evaluation.dsr import deflated_sharpe, hurdle_verdict
from matchscout.evaluation.trial_log import (
    DEFAULT_TRIAL_LOG,
    append_trial,
    load_trials,
    n_distinct_configs,
    sharpe_spread,
    trial_id,
)
from matchscout.forward.ledger import (
    DEFAULT_BETS,
    DEFAULT_SNAPSHOTS,
    NO_ODDS,
    PENDING,
    SETTLED,
    VOID,
    append_snapshot,
    bet_id,
    current_bets,
    place_bets,
    settle_bets,
)
from matchscout.model.goal_model import fit_dixon_coles
from matchscout.value.devig import devig_shin
from matchscout.value.edge import select_value_bets

# Which closing book prices the CLV benchmark, best first. Pinnacle is the sharpest reference and
# the one the backtest uses, but the source stopped carrying it in the current-season files
# (verified 2026-09-20), so the loop falls back and records `clv_book` per bet — a CLV measured
# against a soft book is a weaker yardstick and must not silently pass for a Pinnacle one.
CLV_BOOK_PRIORITY = ("PS", "Avg", "B365")

_PRED_COLUMNS = ["match_id", "p_H", "p_D", "p_A", "p_over", "p_under"]
_1X2 = {"p_H": "H", "p_D": "D", "p_A": "A"}


@dataclass(frozen=True)
class ForwardConfig:
    """The frozen betting configuration. Changing any field is a new trial (D1)."""

    competitions: tuple[str, ...]
    season: str  # current season code — fixture match_ids must match the season CSV's
    history_seasons: tuple[str, ...]  # seasons fetched for training + settlement
    min_train: int = 80
    half_life_days: float = 180.0
    threshold: float = 0.05
    book: str = "B365"
    flat_unit: float = 10.0
    start_bankroll: float = 1000.0
    stale_after_days: int = 14
    min_lead_hours: float = 2.0

    def as_trial_config(self) -> dict[str, Any]:
        return {"harness": "dixon_coles_forward_paper_loop", **asdict(self)}

    @property
    def trial_id(self) -> str:
        return trial_id(self.as_trial_config())


def predict_fixtures(
    history: pd.DataFrame,
    fixtures: pd.DataFrame,
    *,
    as_of: pd.Timestamp,
    half_life_days: float | None,
) -> pd.DataFrame:
    """Fit on played history and return 1X2 + O/U2.5 probabilities for each upcoming fixture.

    Teams with no history (promoted sides, early season) are skipped rather than guessed — the
    same rule the walk-forward backtest applies.
    """
    model = fit_dixon_coles(history, as_of=as_of, half_life_days=half_life_days)
    teams = set(model.teams)
    rows = []
    for fixture in fixtures.itertuples():
        if fixture.home not in teams or fixture.away not in teams:
            continue
        probs = model.predict(fixture.home, fixture.away)
        rows.append(
            {
                "match_id": fixture.match_id,
                "p_H": probs["1x2"]["H"],
                "p_D": probs["1x2"]["D"],
                "p_A": probs["1x2"]["A"],
                "p_over": probs["ou25"]["over"],
                "p_under": probs["ou25"]["under"],
            }
        )
    return pd.DataFrame(rows, columns=_PRED_COLUMNS)


def no_odds_id(match_id: str) -> str:
    """Identity of an un-priced-fixture record.

    Its own namespace on purpose: a `no_odds` row must never occupy the `bet_id` of a real bet,
    or a fixture that had no price this morning could not be bet this evening.
    """
    return f"{match_id}|no_odds"


def _concat(frames: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in columns})
    return pd.concat(non_empty, ignore_index=True)


def _finite(value):
    """NaN -> None: snapshots are read by a browser, and `JSON.parse` rejects a bare NaN."""
    try:
        return None if value is None or not math.isfinite(float(value)) else float(value)
    except (TypeError, ValueError):
        return value


def _played_before(matches: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    played = matches[matches["status"] == "played"]
    if played.empty:
        return played
    dates, ref = align_timestamps(played["date"], now)
    return played[dates < ref]


def _not_yet_kicked_off(
    fixtures: pd.DataFrame, now: pd.Timestamp, min_lead_hours: float
) -> pd.DataFrame:
    """Fixtures still `min_lead_hours` away — a bet is never placed after the whistle.

    The lead time is not caution, it is a correctness margin: football-data.co.uk states kickoff
    in UK local time with no offset, so a naive comparison against a UTC clock can be an hour
    out either way (BST/GMT) and could book a bet on a match already in play. Requiring a
    couple of hours of daylight makes that impossible without guessing the source's timezone.
    """
    if fixtures.empty:
        return fixtures
    stamps = fixtures["timestamp_event"].fillna(fixtures["date"])
    stamps, ref = align_timestamps(stamps, now)
    return fixtures[stamps > ref + pd.Timedelta(hours=min_lead_hours)]


def _closing_lookup(odds: pd.DataFrame) -> dict[tuple[str, str, str], tuple[float, str]]:
    """Best available de-vigged closing probability per selection, with the book it came from."""
    lookup: dict[tuple[str, str, str], tuple[float, str]] = {}
    for book in reversed(CLV_BOOK_PRIORITY):  # worst first, so better books overwrite
        for key, prob in closing_probs(odds, method=devig_shin, book=book).items():
            lookup[key] = (prob, book)
    return lookup


def _outcomes(matches: pd.DataFrame) -> dict[str, tuple[str, str, pd.Timestamp]]:
    played = matches[matches["status"] == "played"]
    out: dict[str, tuple[str, str, pd.Timestamp]] = {}
    for row in played.itertuples():
        hg, ag = int(row.ft_home_goals), int(row.ft_away_goals)
        result = "H" if hg > ag else ("A" if hg < ag else "D")
        out[row.match_id] = (result, "over" if hg + ag >= 3 else "under", row.date)
    return out


def _place_new_bets(
    *,
    config: ForwardConfig,
    history_matches: pd.DataFrame,
    fixture_matches: pd.DataFrame,
    fixture_odds: pd.DataFrame,
    now: pd.Timestamp,
    run_id: str,
    bets_path: Path | str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    unpriced: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for competition in config.competitions:
        history = _played_before(
            history_matches[history_matches["competition"] == competition], now
        )
        upcoming = _not_yet_kicked_off(
            fixture_matches[fixture_matches["competition"] == competition],
            now,
            config.min_lead_hours,
        )
        if upcoming.empty:
            continue
        if len(history) < config.min_train:
            skipped.append(
                {
                    "competition": competition,
                    "reason": f"burn-in not reached ({len(history)} < {config.min_train})",
                    "n_fixtures": int(len(upcoming)),
                }
            )
            continue

        preds = predict_fixtures(
            history, upcoming, as_of=now, half_life_days=config.half_life_days
        )
        if preds.empty:
            continue
        comp_odds = fixture_odds[fixture_odds["match_id"].isin(set(upcoming["match_id"]))]
        picks = select_value_bets(
            preds, comp_odds, threshold=config.threshold, book=config.book
        )
        kickoff = dict(zip(upcoming["match_id"], upcoming["date"], strict=False))

        for pick in picks.itertuples():
            rows.append(
                {
                    "bet_id": bet_id(pick.match_id, pick.market, pick.selection),
                    "match_id": pick.match_id,
                    "competition": competition,
                    "date": str(kickoff.get(pick.match_id))[:10],
                    "market": pick.market,
                    "selection": pick.selection,
                    "book": config.book,
                    "odds_taken": float(pick.odds),
                    "p_model": float(pick.p_model),
                    "edge": float(pick.edge),
                    "stake": config.flat_unit,
                    "timestamp_known": now.isoformat(),
                    "status": PENDING,
                    "run_id": run_id,
                    "trial_id": config.trial_id,
                }
            )

        # Honest record of what could not be priced: predicted, but no price at the book.
        priced = set(
            comp_odds[
                (comp_odds["book"] == config.book) & (~comp_odds["is_closing"].astype(bool))
            ]["match_id"]
        )
        for pred in preds[~preds["match_id"].isin(priced)].itertuples():
            probs = {column: getattr(pred, column) for column in _1X2}
            best = max(probs, key=probs.__getitem__)
            unpriced.append(
                {
                    "bet_id": no_odds_id(pred.match_id),
                    "match_id": pred.match_id,
                    "competition": competition,
                    "date": str(kickoff.get(pred.match_id))[:10],
                    "market": "1x2",
                    "selection": _1X2[best],
                    "book": config.book,
                    "odds_taken": None,
                    "p_model": float(probs[best]),
                    "edge": None,
                    "stake": 0.0,
                    "timestamp_known": now.isoformat(),
                    "status": NO_ODDS,
                    "run_id": run_id,
                    "trial_id": config.trial_id,
                    "note": f"no {config.book} pre-match price in the fixtures feed",
                }
            )

    placed = place_bets(bets_path, rows)
    recorded = place_bets(bets_path, unpriced)
    return {"placed": placed, "no_odds": recorded, "skipped": skipped}


def _settle_pending(
    *,
    config: ForwardConfig,
    history_matches: pd.DataFrame,
    history_odds: pd.DataFrame,
    now: pd.Timestamp,
    bets_path: Path | str,
) -> dict[str, Any]:
    bets = current_bets(bets_path)
    if bets.empty:
        return {"settled": [], "voided": []}
    pending = bets[bets["status"] == PENDING]
    if pending.empty:
        return {"settled": [], "voided": []}

    outcomes = _outcomes(history_matches)
    closing = _closing_lookup(history_odds)
    settlements: list[dict[str, Any]] = []
    voids: list[dict[str, Any]] = []

    for bet in pending.itertuples():
        result = outcomes.get(bet.match_id)
        if result is None:
            kickoff, ref = align_timestamps(pd.Series([pd.Timestamp(bet.date)]), now)
            if (ref - kickoff.iloc[0]).days > config.stale_after_days:
                voids.append(
                    {
                        "bet_id": bet.bet_id,
                        "status": VOID,
                        "won": None,
                        "pnl": 0.0,
                        "settled_at": now.isoformat(),
                        "note": (
                            f"no result {config.stale_after_days} days after kickoff — "
                            "postponed, abandoned or renamed; stake returned"
                        ),
                    }
                )
            continue

        actual = result[0] if bet.market == "1x2" else result[1]
        won = bool(bet.selection == actual)
        stake, odds = float(bet.stake), float(bet.odds_taken)
        p_close, clv_book = closing.get((bet.match_id, bet.market, bet.selection), (None, None))
        settlements.append(
            {
                "bet_id": bet.bet_id,
                "status": SETTLED,
                "won": won,
                "pnl": stake * (odds - 1.0) if won else -stake,
                "settled_at": now.isoformat(),
                "clv_book": clv_book,
                "p_close": p_close,
                "clv": (p_close * odds - 1.0) if p_close is not None else None,
                "clv_beat": bool(p_close * odds - 1.0 > 0) if p_close is not None else None,
            }
        )

    written = settle_bets(bets_path, settlements + voids)
    return {
        "settled": [w for w in written if w["status"] == SETTLED],
        "voided": [w for w in written if w["status"] == VOID],
    }


def settled_ledger(bets: pd.DataFrame, start_bankroll: float) -> pd.DataFrame:
    """Settled bets in the shape `backtest.metrics.summary` expects (same metric definitions)."""
    columns = ["date", "market", "selection", "odds_taken", "stake", "won", "pnl", "clv"]
    if bets.empty:
        frame = pd.DataFrame({c: pd.Series(dtype="object") for c in columns})
        frame["bankroll_after"] = pd.Series(dtype=float)
        frame["clv_beat"] = pd.Series(dtype=bool)
        return frame
    done = bets[bets["status"] == SETTLED].copy()
    if done.empty:
        return settled_ledger(pd.DataFrame(), start_bankroll)
    done["date"] = pd.to_datetime(done["date"])
    done = done.sort_values(["date", "bet_id"])
    done["pnl"] = done["pnl"].astype(float)
    done["stake"] = done["stake"].astype(float)
    done["clv"] = pd.to_numeric(done["clv"], errors="coerce")
    done["clv_beat"] = done["clv"] > 0
    done["bankroll_after"] = start_bankroll + done["pnl"].cumsum()
    return done


def _log_config_once(config: ForwardConfig, trial_log_path: Path | str) -> bool:
    """Log the forward config as a trial the first time it is seen; return True if written.

    Once per config, not once per run: a daily cron re-running the same frozen config is not a
    new attempt at finding an edge, and inflating the trial count would make the hurdle
    meaningless in the other direction.
    """
    known = {t["trial_id"] for t in load_trials(trial_log_path) if t.get("kind") == "forward"}
    if config.trial_id in known:
        return False
    append_trial(
        trial_log_path,
        config=config.as_trial_config(),
        metrics={"n_bets": 0, "sharpe": None},
        kind="forward",
        note="forward paper loop — config frozen at first run; results live in data/bets.jsonl",
    )
    return True


def run_forward(
    *,
    now: pd.Timestamp,
    history: HistoryProvider,
    fixtures: FixtureProvider,
    config: ForwardConfig,
    bets_path: Path | str = DEFAULT_BETS,
    snapshots_path: Path | str = DEFAULT_SNAPSHOTS,
    trial_log_path: Path | str = DEFAULT_TRIAL_LOG,
) -> dict[str, Any]:
    """Advance the paper loop by one run. Safe to call any number of times per day."""
    now = pd.Timestamp(now)
    run_id = now.strftime("%Y-%m-%d")
    logged_config = _log_config_once(config, trial_log_path)

    history_matches = _concat(
        [
            history.fetch_matches(competition, season)
            for competition in config.competitions
            for season in config.history_seasons
        ],
        MATCH_COLUMNS,
    )
    history_odds = _concat(
        [
            history.fetch_odds(competition, season)
            for competition in config.competitions
            for season in config.history_seasons
        ],
        ODDS_COLUMNS,
    )

    fixture_pairs = [
        fixtures.fetch_upcoming(competition, config.season)
        for competition in config.competitions
    ]
    fixture_matches = _concat([pair[0] for pair in fixture_pairs], MATCH_COLUMNS)
    fixture_odds = _concat([pair[1] for pair in fixture_pairs], ODDS_COLUMNS)

    placement = _place_new_bets(
        config=config,
        history_matches=history_matches,
        fixture_matches=fixture_matches,
        fixture_odds=fixture_odds,
        now=now,
        run_id=run_id,
        bets_path=bets_path,
    )
    settlement = _settle_pending(
        config=config,
        history_matches=history_matches,
        history_odds=history_odds,
        now=now,
        bets_path=bets_path,
    )

    bets = current_bets(bets_path)
    ledger = settled_ledger(bets, config.start_bankroll)
    record = summary(ledger)
    returns = (ledger["pnl"] / ledger["stake"]) if not ledger.empty else pd.Series(dtype=float)
    trials = load_trials(trial_log_path)
    dsr = deflated_sharpe(
        returns, n_trials=n_distinct_configs(trials), sr_std=sharpe_spread(trials)
    )

    snapshot = {
        "run_id": run_id,
        "as_of": now.isoformat(),
        "trial_id": config.trial_id,
        "bankroll": float(
            ledger["bankroll_after"].iloc[-1] if not ledger.empty else config.start_bankroll
        ),
        "n_settled": int(record.get("n_bets", 0)),
        "n_pending": int((bets["status"] == PENDING).sum()) if not bets.empty else 0,
        "n_no_odds": int((bets["status"] == NO_ODDS).sum()) if not bets.empty else 0,
        "n_void": int((bets["status"] == VOID).sum()) if not bets.empty else 0,
        "total_staked": _finite(record.get("total_staked", 0.0)),
        "profit": _finite(record.get("profit", 0.0)),
        "yield": _finite(record.get("yield")),
        "clv_mean": _finite(record.get("clv_mean")),
        "clv_beat_rate": _finite(record.get("clv_beat_rate")),
    }
    append_snapshot(snapshots_path, snapshot)

    return {
        "run_id": run_id,
        "as_of": now.isoformat(),
        "config": config.as_trial_config(),
        "trial_id": config.trial_id,
        "config_newly_logged": logged_config,
        "n_placed": len(placement["placed"]),
        "n_no_odds": len(placement["no_odds"]),
        "n_settled_now": len(settlement["settled"]),
        "n_voided_now": len(settlement["voided"]),
        "skipped_competitions": placement["skipped"],
        "record": record,
        "verdict": verdict(record),
        "trials_adjusted": {**dsr, "verdict": hurdle_verdict(dsr)},
        "snapshot": snapshot,
    }
