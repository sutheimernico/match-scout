"""Walk-forward value-betting backtest — the core "would the slips have hit?" run.

    uv run python scripts/run_backtest.py --competitions E0 --seasons 2223 --seasons 2324

Pipeline: fetch (cached) -> walk-forward Dixon-Coles predictions -> value bets (EV edge on the
Bet365 pre-match price) -> settle at the taken price with flat + Kelly staking -> yield-with-CI,
CLV, drawdown, verdict, all vs. naive baselines. The expected honest finding is no positive-yield
edge and a sub-50% CLV beat-rate against the closing line.

Every invocation appends one entry to the trial log (`data/trial_log.jsonl`) — unconditionally,
there is no flag to skip it (council D1). The trials-adjusted DSR hurdle in the summary is then
computed over the whole log, so each extra configuration tried makes the bar for claiming an
edge strictly higher.
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
from matchscout.backtest.placebo import market_null_test
from matchscout.data.football_data_co_uk import FootballDataCoUk
from matchscout.evaluation.dsr import deflated_sharpe, hurdle_verdict, sharpe_ratio
from matchscout.evaluation.trial_log import (
    DEFAULT_TRIAL_LOG,
    append_trial,
    load_trials,
    n_distinct_configs,
    sharpe_spread,
)
from matchscout.evaluation.walk_forward import walk_forward_predict
from matchscout.value.edge import select_value_bets

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")


def bet_returns(ledger: pd.DataFrame) -> pd.Series:
    """Per-bet return on stake — the observation series the Sharpe/DSR hurdle runs on."""
    if ledger.empty:
        return pd.Series(dtype=float)
    return ledger["pnl"].astype(float) / ledger["stake"].astype(float)


@app.command()
def main(
    competitions: Annotated[list[str], typer.Option()],
    seasons: Annotated[list[str], typer.Option()],
    min_train: Annotated[int, typer.Option()] = 80,
    half_life_days: Annotated[float, typer.Option()] = 180.0,
    threshold: Annotated[float, typer.Option(help="Minimum edge to bet.")] = 0.05,
    flat_unit: Annotated[float, typer.Option()] = 10.0,
    trial_log: Annotated[
        Path, typer.Option(help="Append-only trial log (D1).")
    ] = DEFAULT_TRIAL_LOG,
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
    flat_returns = pd.Series(dtype=float)
    for scheme in ("flat", "kelly"):
        ledger = settle_bets(picks, matches, odds, staking=scheme, flat_unit=flat_unit)
        summ = summary(ledger)
        result[scheme] = {**summ, "verdict": verdict(summ)}
        if scheme == "flat":
            flat_returns = bet_returns(ledger)

    result["baselines_flat_yield"] = {}
    for strategy in ("home", "favorite", "over"):
        bp = baseline_picks(matches, odds, strategy)
        bl = settle_bets(bp, matches, odds, staking="flat", flat_unit=flat_unit)
        result["baselines_flat_yield"][strategy] = summary(bl).get("yield")

    # Leak guard: the real yield should sit inside the market-implied null (no edge).
    result["market_null"] = market_null_test(picks, matches, odds, n=1000, flat_unit=flat_unit)

    # D1: this run is a trial. Log it first, then judge it against the whole logged search.
    config = {
        "harness": "dixon_coles_value_backtest",
        "competitions": sorted(competitions),
        "seasons": sorted(seasons),
        "min_train": min_train,
        "half_life_days": half_life_days,
        "threshold": threshold,
        "book": "B365",
        "staking": "flat",
        "flat_unit": flat_unit,
    }
    flat = result["flat"]
    append_trial(
        trial_log,
        config=config,
        metrics={
            "n_bets": flat.get("n_bets", 0),
            "yield": flat.get("yield"),
            "yield_ci": flat.get("yield_ci"),
            "clv_mean": flat.get("clv_mean"),
            "clv_beat_rate": flat.get("clv_beat_rate"),
            "sharpe": sharpe_ratio(flat_returns),
        },
        note="scripts/run_backtest.py",
    )
    trials = load_trials(trial_log)
    dsr = deflated_sharpe(
        flat_returns,
        n_trials=n_distinct_configs(trials),
        sr_std=sharpe_spread(trials),
    )
    result["trials_adjusted"] = {**dsr, "verdict": hurdle_verdict(dsr)}

    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
