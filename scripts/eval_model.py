"""Walk-forward calibration of the goal model vs. the closing line, per competition-season.

    uv run python scripts/eval_model.py --competitions E0 --seasons 2223 --seasons 2324

Fetches (cached) from football-data.co.uk, walk-forward-predicts with Dixon-Coles, and reports
Brier + log-loss for the model against the Shin-de-vigged Pinnacle closing line. The expected
honest finding is that the model does NOT beat the closing line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.data.football_data_co_uk import FootballDataCoUk
from matchscout.evaluation.calibration import calibration_report
from matchscout.evaluation.walk_forward import walk_forward_predict

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")


@app.command()
def main(
    competitions: Annotated[list[str], typer.Option()],
    seasons: Annotated[list[str], typer.Option()],
    min_train: Annotated[int, typer.Option()] = 60,
    half_life_days: Annotated[float, typer.Option()] = 180.0,
) -> None:
    provider = FootballDataCoUk(CACHE)
    matches = pd.concat(
        [provider.fetch_matches(c, s) for c in competitions for s in seasons], ignore_index=True
    )
    odds = pd.concat(
        [provider.fetch_odds(c, s) for c in competitions for s in seasons], ignore_index=True
    )
    preds = walk_forward_predict(matches, min_train=min_train, half_life_days=half_life_days)
    typer.echo(f"predicted {len(preds)} matches")
    typer.echo(json.dumps(calibration_report(preds, odds), indent=2))


if __name__ == "__main__":
    app()
