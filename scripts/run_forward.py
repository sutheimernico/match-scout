"""Advance the forward paper loop by one run — the live, un-hindsightable half of the harness.

    uv run python scripts/run_forward.py                      # Top-5, current season, today
    uv run python scripts/run_forward.py --competitions E0 --now 2026-09-20T09:00:00Z

PAPER STAKES ONLY. This writes a JSONL ledger under `data/`; it has no broker, no account and no
way to place a real bet.

Safe to run as often as you like: placement is keyed by fixture-market-selection and settlement
only touches pending bets, so a second run on the same day is a no-op. That is what makes it
cron-safe (`.github/workflows/pipeline.yml`).

Sources, both free and key-free: upcoming fixtures WITH pre-match prices from
football-data.co.uk's fixtures feed, results + closing prices from its season CSVs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.data.football_data_co_uk import (
    FootballDataCoUk,
    FootballDataCoUkFixtures,
    previous_season_code,
    season_code,
)
from matchscout.forward.ledger import DEFAULT_BETS, DEFAULT_SNAPSHOTS
from matchscout.forward.loop import ForwardConfig, run_forward

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")
TOP5 = ["E0", "SP1", "D1", "I1", "F1"]


@app.command()
def main(
    competitions: Annotated[
        list[str] | None, typer.Option(help="Default = the Top-5 leagues.")
    ] = None,
    season: Annotated[
        str, typer.Option(help="Season code; default = the one covering --now.")
    ] = "",
    history_seasons: Annotated[
        list[str] | None, typer.Option(help="Seasons to train on; default = previous + current.")
    ] = None,
    now: Annotated[str, typer.Option(help="Run timestamp (ISO); default = now, UTC.")] = "",
    min_train: Annotated[int, typer.Option()] = 80,
    half_life_days: Annotated[float, typer.Option()] = 180.0,
    threshold: Annotated[float, typer.Option()] = 0.05,
    flat_unit: Annotated[float, typer.Option()] = 10.0,
    bets_path: Annotated[Path, typer.Option()] = DEFAULT_BETS,
    snapshots_path: Annotated[Path, typer.Option()] = DEFAULT_SNAPSHOTS,
) -> None:
    run_at = pd.Timestamp(now) if now else pd.Timestamp.now(tz="UTC")
    current = season or season_code(run_at)
    history = tuple(history_seasons or ()) or (previous_season_code(current), current)

    config = ForwardConfig(
        competitions=tuple(competitions or TOP5),
        season=current,
        history_seasons=history,
        min_train=min_train,
        half_life_days=half_life_days,
        threshold=threshold,
        flat_unit=flat_unit,
    )
    result = run_forward(
        now=run_at,
        history=FootballDataCoUk(CACHE, live_seasons={current}),
        fixtures=FootballDataCoUkFixtures(CACHE, run_date=run_at),
        config=config,
        bets_path=bets_path,
        snapshots_path=snapshots_path,
    )
    typer.echo(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    app()
