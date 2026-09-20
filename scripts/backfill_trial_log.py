"""Backfill the trial log with the configurations that were run before it existed (D1).

The trial log only deters cherry-picking if it covers the whole history, not just the runs made
after it was built. These entries reconstruct what the record shows was actually run on
2026-07-05 — the numbers come from `PLAN.md` (Phase 4 acceptance) and the committed
`site/public/data/backtest.json`, and every entry is flagged `backfilled: true` so nobody
mistakes reconstruction for observation.

`sharpe` is null on backfilled entries: the per-bet return series was never retained, and
inventing one would defeat the point of the log. The DSR then falls back to its null sampling
deviation, which is the conservative direction.

Idempotent — re-running adds nothing. Run: uv run python scripts/backfill_trial_log.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer

from matchscout.evaluation.trial_log import (
    DEFAULT_TRIAL_LOG,
    append_trial,
    load_trials,
    trial_id,
)

app = typer.Typer(add_completion=False)

RUN_DATE = pd.Timestamp("2026-07-05T23:00:00Z")
CODE_VERSION = "cf0498e"  # last commit of the 2026-07-05 autopilot session

_BASE = {
    "harness": "dixon_coles_value_backtest",
    "seasons": ["2223", "2324"],
    "min_train": 80,
    "half_life_days": 180.0,
    "threshold": 0.05,
    "book": "B365",
    "staking": "flat",
    "flat_unit": 10.0,
}
TOP5 = ["D1", "E0", "F1", "I1", "SP1"]

# (config, metrics, kind, note) — the historical record, nothing recomputed.
HISTORICAL: list[tuple[dict, dict, str, str]] = [
    (
        {**_BASE, "competitions": ["E0"]},
        {
            "n_bets": 971,
            "yield": -0.047,
            "yield_ci": [-0.130, 0.041],
            "clv_mean": -0.054,
            "clv_beat_rate": 0.204,
            "sharpe": None,
        },
        "backtest",
        "PLAN.md Phase 4 acceptance — the first real run (E0 only).",
    ),
    (
        {**_BASE, "competitions": TOP5},
        {
            "n_bets": 4540,
            "yield": -0.08780176211453745,
            "yield_ci": [-0.12767428414096918, -0.04823953744493395],
            "clv_mean": -0.05158138371353676,
            "clv_beat_rate": 0.22433208213733716,
            "sharpe": None,
        },
        "backtest",
        "site/public/data/backtest.json — the Top-5 headline run.",
    ),
]

# Per-league cuts of the Top-5 run. D1 counts a subgroup slice as a trial: five ways to look at
# one result are five chances to find a flattering one. The Premier League slice reproduces the
# E0 run above bet-for-bet; it is still logged separately, which over- rather than under-counts
# the search — the conservative direction.
SLICES = [
    ("E0", "Premier League", 971, -0.047260556127703385, 0.20351239669421486),
    ("SP1", "La Liga", 953, -0.15189926547743968, 0.21091290661070305),
    ("D1", "Bundesliga", 721, -0.1944660194174757, 0.20476858345021037),
    ("I1", "Serie A", 911, -0.04504939626783755, 0.23600439077936333),
    ("F1", "Ligue 1", 984, -0.02715447154471544, 0.2611788617886179),
]
for _code, _name, _n, _y, _clv in SLICES:
    HISTORICAL.append(
        (
            {**_BASE, "competitions": TOP5, "slice_league": _code},
            {"n_bets": _n, "yield": _y, "clv_beat_rate": _clv, "sharpe": None},
            "slice",
            f"site/public/data/backtest.json per_league cut: {_name}.",
        )
    )


@app.command()
def main(
    trial_log: Path = DEFAULT_TRIAL_LOG,
) -> None:
    known = {t["trial_id"] for t in load_trials(trial_log) if t.get("backfilled")}
    added = 0
    for config, metrics, kind, note in HISTORICAL:
        if trial_id(config) in known:
            continue
        append_trial(
            trial_log,
            config=config,
            metrics=metrics,
            kind=kind,
            code_version=CODE_VERSION,
            note=note,
            backfilled=True,
            now=RUN_DATE,
        )
        added += 1
    typer.echo(f"{trial_log}: {added} backfilled entr{'y' if added == 1 else 'ies'} added")


if __name__ == "__main__":
    app()
