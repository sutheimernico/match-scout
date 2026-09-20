"""Append-only trial log — every configuration ever run stays on the record (council D1).

Why this exists: the harness has free knobs (edge threshold, burn-in, time-decay half-life,
staking, league/market scope). Anyone who runs N configurations and reports the best one has
not found an edge, they have found a maximum. The defence is to make the search itself
visible: every backtest run appends one entry here, unconditionally and with no flag to skip
it, and the significance hurdle (`evaluation/dsr.py`) rises with the number of entries.
Subgroup slices (per-league, per-market) count as trials too — that is the D1 requirement.

Storage: JSON Lines under `data/trial_log.jsonl`, a derived artifact (no raw source data), so
it is committed and grows with the project's history.

One JSON object per line:

    trial_id      str    sha256[:12] over the canonical config — identical config, identical id
    logged_at     str    ISO-8601 UTC timestamp of the run
    kind          str    "backtest" (a headline run) | "slice" (a subgroup cut — also a trial)
    config        dict   the full parameter set the run used
    metrics       dict   headline metrics (n_bets, yield, yield_ci, clv_mean, clv_beat_rate, ...)
    code_version  str    git commit the run used, or "unknown"
    backfilled    bool   true = reconstructed from the written record, not observed live
    note          str    free-text provenance, "" when unset

A repeated identical config is appended again rather than deduped: re-running a config is a
real event, and the count of *distinct* configs is what the DSR hurdle uses.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_TRIAL_LOG = Path("data/trial_log.jsonl")

ENTRY_FIELDS = (
    "trial_id",
    "logged_at",
    "kind",
    "config",
    "metrics",
    "code_version",
    "backfilled",
    "note",
)


def _canonical(config: dict[str, Any]) -> str:
    """Order-independent JSON rendering of a config (so key order cannot change the id)."""
    return json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)


def trial_id(config: dict[str, Any]) -> str:
    """Stable short hash of a configuration."""
    return hashlib.sha256(_canonical(config).encode("utf-8")).hexdigest()[:12]


def git_commit(repo: Path | None = None) -> str:
    """Short git commit of the working tree, or "unknown" outside a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo or Path.cwd(),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def append_trial(
    path: Path | str,
    *,
    config: dict[str, Any],
    metrics: dict[str, Any],
    kind: str = "backtest",
    code_version: str | None = None,
    note: str = "",
    backfilled: bool = False,
    now: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Append one trial entry and return it. Creates the file (and parents) on first use."""
    entry = {
        "trial_id": trial_id(config),
        "logged_at": (now or pd.Timestamp.now(tz="UTC")).isoformat(),
        "kind": kind,
        "config": config,
        "metrics": metrics,
        "code_version": code_version if code_version is not None else git_commit(),
        "backfilled": bool(backfilled),
        "note": note,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
    return entry


def load_trials(path: Path | str) -> list[dict[str, Any]]:
    """Read every logged trial (empty list when the log does not exist yet)."""
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def n_distinct_configs(trials: Iterable[dict[str, Any]]) -> int:
    """Number of distinct configurations tried — the N the DSR hurdle is deflated by."""
    return len({t["trial_id"] for t in trials})


def sharpe_spread(trials: Iterable[dict[str, Any]]) -> float | None:
    """Sample std of the per-bet Sharpe ratios across distinct configs (None below two).

    This is the `V[SR]` the Deflated Sharpe Ratio needs: how far apart the tried configs'
    Sharpes actually landed. Measured beats assumed — the fallback is the null sampling
    deviation, which is usually the more optimistic of the two.
    """
    by_id: dict[str, float] = {}
    for trial in trials:
        value = (trial.get("metrics") or {}).get("sharpe")
        if value is None:
            continue
        value = float(value)
        if math.isfinite(value):
            by_id[trial["trial_id"]] = value
    if len(by_id) < 2:
        return None
    return float(statistics.stdev(by_id.values()))
