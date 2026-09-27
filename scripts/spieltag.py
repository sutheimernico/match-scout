"""Build the forward surfaces from the committed logs: the German Spieltag page + forward.json.

    uv run python scripts/spieltag.py

Reads `data/bets.jsonl` + `data/predictions.jsonl` (no network, no refit) and writes
  - site/public/spieltag.html   — German matchday page; opens from disk or via the dashboard
  - site/public/data/forward.json — the forward record the dashboard's panel renders
Run it after `scripts/run_forward.py`; `scripts/run_matchday.sh` chains both.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.forward.ledger import DEFAULT_BETS, current_bets
from matchscout.forward.predictions import DEFAULT_PREDICTIONS, current_predictions
from matchscout.forward.report import forward_record
from matchscout.forward.spieltag import render_spieltag

app = typer.Typer(add_completion=False)
SITE_PUBLIC = Path("site/public")


@app.command()
def main(
    bets_path: Annotated[Path, typer.Option()] = DEFAULT_BETS,
    predictions_path: Annotated[Path, typer.Option()] = DEFAULT_PREDICTIONS,
    out_dir: Annotated[Path, typer.Option()] = SITE_PUBLIC,
) -> None:
    now = pd.Timestamp.now(tz="UTC")
    bets = current_bets(bets_path)
    predictions = current_predictions(predictions_path)
    record = {"generated_at": now.isoformat(), **forward_record(bets, predictions)}

    backtest_path = out_dir / "data" / "backtest.json"
    backtest = json.loads(backtest_path.read_text()) if backtest_path.exists() else None

    (out_dir / "data").mkdir(parents=True, exist_ok=True)
    (out_dir / "data" / "forward.json").write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n"
    )
    page = render_spieltag(bets, predictions, record, now=now, backtest=backtest)
    (out_dir / "spieltag.html").write_text(page, encoding="utf-8")
    b = record["bets"]
    typer.echo(
        f"forward: state={record['state']} bets settled={b['n_bets']} pending={b['n_pending']} "
        f"predictions settled={record['calibration']['n']} -> {out_dir}/spieltag.html"
    )


if __name__ == "__main__":
    app()
