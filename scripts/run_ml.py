"""Evaluate the walled-off ML challenger vs. Dixon-Coles vs. the closing line.

    uv run python scripts/run_ml.py --competitions E0 --seasons 2223 --seasons 2324

Walk-forward Dixon-Coles predictions -> 1X2 feature dataset -> LightGBM over purged/embargoed
folds -> OOS Brier/log-loss vs. Dixon-Coles and the market. Expected honest finding: the naive
GBDT does not beat the statistical baseline or the closing line (it tends to overfit small data).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.data.football_data_co_uk import FootballDataCoUk
from matchscout.evaluation.walk_forward import walk_forward_predict
from matchscout.ml.evaluate import evaluate_challenger

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")


@app.command()
def main(
    competitions: Annotated[list[str], typer.Option()],
    seasons: Annotated[list[str], typer.Option()],
    min_train: Annotated[int, typer.Option()] = 80,
    half_life_days: Annotated[float, typer.Option()] = 180.0,
    n_estimators: Annotated[int, typer.Option()] = 200,
) -> None:
    provider = FootballDataCoUk(CACHE)
    matches = pd.concat(
        [provider.fetch_matches(c, s) for c in competitions for s in seasons], ignore_index=True
    )
    odds = pd.concat(
        [provider.fetch_odds(c, s) for c in competitions for s in seasons], ignore_index=True
    )
    preds = walk_forward_predict(matches, min_train=min_train, half_life_days=half_life_days)
    typer.echo(json.dumps(evaluate_challenger(preds, odds, n_estimators=n_estimators), indent=2))


if __name__ == "__main__":
    app()
