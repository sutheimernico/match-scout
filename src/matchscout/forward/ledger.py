"""Append-only paper-bet ledger + bankroll snapshots (PROJECT.md §4 canonical tables).

Paper stakes only — nothing here places, or can place, a real bet.

Storage is an **event log**, not a mutable table: every line in `data/bets.jsonl` is one version
of one bet, and the current state of a bet is its last line. A bet is written once when it is
placed (`pending`) and once more when it settles (`settled` / `void`), so the file never rewrites
history — what the loop believed at placement time stays readable next to what happened. The
alternative (rewriting rows in place) would quietly destroy the audit trail that is the whole
point of a forward proof.

Idempotency lives here rather than in the loop: `place_bets` ignores a `bet_id` that already
exists, `settle_bets` ignores anything not currently pending. Running the loop twice in a day,
or twice in a minute, therefore changes nothing.

`bet_id` = "<match_id>|<market>|<selection>" — deterministic and human-readable. It deliberately
does NOT include the timestamp: one fixture-market-selection is one paper bet, forever. Seeing a
better price tomorrow does not create a second bet, it is just a price the harness did not take.

Bet fields (`BET_COLUMNS`), a subset of PROJECT.md's `bets`:

    bet_id, match_id, competition, date (kickoff day), market, selection
    book, odds_taken, p_model, edge, stake, timestamp_known, status, run_id, trial_id
    won, pnl, settled_at, clv_book, p_close, clv, clv_beat, note

`status` is one of:
    pending  — placed, fixture not played yet
    settled  — result known, `won`/`pnl` filled
    void     — no result found in time (postponement / renamed fixture); stake returned
    no_odds  — the fixture was predicted but no price existed at the selection book: recorded
               honestly as an un-priced opportunity, stake 0, NEVER an invented price

Snapshots (`data/bankroll_snapshots.jsonl`) are one append-only row per run: the bankroll and the
running record at that moment.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_BETS = Path("data/bets.jsonl")
DEFAULT_SNAPSHOTS = Path("data/bankroll_snapshots.jsonl")

BET_COLUMNS = [
    "bet_id",
    "match_id",
    "competition",
    "date",
    "market",
    "selection",
    "book",
    "odds_taken",
    "p_model",
    "edge",
    "stake",
    "timestamp_known",
    "status",
    "run_id",
    "trial_id",
    "won",
    "pnl",
    "settled_at",
    "clv_book",
    "p_close",
    "clv",
    "clv_beat",
    "note",
]

PENDING = "pending"
SETTLED = "settled"
VOID = "void"
NO_ODDS = "no_odds"


def bet_id(match_id: str, market: str, selection: str) -> str:
    """Deterministic identity of a paper bet: one per fixture-market-selection, forever."""
    return f"{match_id}|{market}|{selection}"


def _read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _append_jsonl(path: Path | str, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    return len(rows)


def load_events(path: Path | str = DEFAULT_BETS) -> list[dict[str, Any]]:
    """Every ledger event ever written, in order."""
    return _read_jsonl(path)


def current_bets(path: Path | str = DEFAULT_BETS) -> pd.DataFrame:
    """Fold the event log to one row per bet (its latest state)."""
    state: dict[str, dict[str, Any]] = {}
    for event in load_events(path):
        state[event["bet_id"]] = event
    if not state:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in BET_COLUMNS})
    return pd.DataFrame(list(state.values()))


def place_bets(path: Path | str, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append bets whose `bet_id` is not in the ledger yet; return the ones actually written."""
    known = {event["bet_id"] for event in load_events(path)}
    fresh: list[dict[str, Any]] = []
    seen_now: set[str] = set()
    for row in rows:
        bid = row["bet_id"]
        if bid in known or bid in seen_now:
            continue
        seen_now.add(bid)
        fresh.append({column: row.get(column) for column in BET_COLUMNS})
    _append_jsonl(path, fresh)
    return fresh


def settle_bets(path: Path | str, settlements: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append settlement events for bets that are currently pending; return what was written.

    A settlement carries the fields that change (`status`, `won`, `pnl`, CLV, ...) and is merged
    onto the bet's last known state, so the new event is a complete row on its own.
    """
    state = {event["bet_id"]: event for event in load_events(path)}
    written: list[dict[str, Any]] = []
    for settlement in settlements:
        bid = settlement["bet_id"]
        previous = state.get(bid)
        if previous is None or previous.get("status") != PENDING:
            continue
        merged = {**previous, **settlement}
        row = {column: merged.get(column) for column in BET_COLUMNS}
        state[bid] = row
        written.append(row)
    _append_jsonl(path, written)
    return written


def append_snapshot(path: Path | str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Append one bankroll snapshot row."""
    _append_jsonl(path, [snapshot])
    return snapshot


def load_snapshots(path: Path | str = DEFAULT_SNAPSHOTS) -> list[dict[str, Any]]:
    """Every bankroll snapshot ever written, in order."""
    return _read_jsonl(path)
