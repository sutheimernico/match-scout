"""Walk-forward value-betting backtest — the core "would the slips have hit?" run.

    uv run python scripts/run_backtest.py --competitions E0 --seasons 2223 --seasons 2324

Pipeline: fetch (cached) -> walk-forward Dixon-Coles predictions -> value bets (EV edge on the
Bet365 pre-match price) -> settle at the taken price with flat + Kelly staking -> yield-with-CI,
CLV, drawdown, verdict, all vs. naive baselines. The expected honest finding is no positive-yield
edge and a sub-50% CLV beat-rate against the closing line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.backtest.baselines import baseline_picks
from matchscout.backtest.engine import settle_bets
from matchscout.backtest.metrics import summary, verdict
from matchscout.data.football_data_co_uk import FootballDataCoUk
from matchscout.evaluation.walk_forward import walk_forward_predict
from matchscout.value.edge import select_value_bets

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")


@app.command()
def main(
    competitions: Annotated[list[str], typer.Option()],
    seasons: Annotated[list[str], typer.Option()],
    min_train: Annotated[int, typer.Option()] = 80,
    half_life_days: Annotated[float, typer.Option()] = 180.0,
    threshold: Annotated[float, typer.Option(help="Minimum edge to bet.")] = 0.05,
    flat_unit: Annotated[float, typer.Option()] = 10.0,
) -> None:
    provider = FootballDataCoUk(CACHE)
    matches = pd.concat(
        [provider.fetch_matches(c, s) for c in competitions for s in seasons], ignore_index=True
    )
    odds = pd.concat(
        [provider.fetch_odds(c, s) for c in competitions for s in seasons], ignore_index=True
    )

    preds = walk_forward_predict(matches, min_train=min_train, half_life_days=half_life_days)
    picks = select_value_bets(preds, odds, threshold=threshold, book="B365")

    result: dict = {"n_predicted": int(len(preds)), "n_value_bets": int(len(picks))}
    for scheme in ("flat", "kelly"):
        ledger = settle_bets(picks, matches, odds, staking=scheme, flat_unit=flat_unit)
        summ = summary(ledger)
        result[scheme] = {**summ, "verdict": verdict(summ)}

    result["baselines_flat_yield"] = {}
    for strategy in ("home", "favorite", "over"):
        bp = baseline_picks(matches, odds, strategy)
        bl = settle_bets(bp, matches, odds, staking="flat", flat_unit=flat_unit)
        result["baselines_flat_yield"][strategy] = summary(bl).get("yield")

    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
