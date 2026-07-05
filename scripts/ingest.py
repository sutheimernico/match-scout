"""Ingest Top-5 league season CSVs into canonical Parquet under .cache/canonical/.

Raw and canonical data both stay in .cache/ (gitignored) — football-data.co.uk data is
not redistributable. Only truly-derived artifacts (bet ledger, ROI snapshots) go to data/.

    uv run python scripts/ingest.py --seasons 2324 --seasons 2223
    uv run python scripts/ingest.py --seasons 2324 --competitions E0 --competitions D1
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.data.football_data_co_uk import DIVISIONS, FootballDataCoUk

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")


@app.command()
def main(
    seasons: Annotated[list[str], typer.Option(help="Season codes, e.g. 2324 2223.")],
    competitions: Annotated[
        list[str] | None, typer.Option(help="Default: all Top-5.")
    ] = None,
) -> None:
    comps = competitions or list(DIVISIONS)
    provider = FootballDataCoUk(CACHE)
    out_dir = CACHE / "canonical"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_matches: list[pd.DataFrame] = []
    all_odds: list[pd.DataFrame] = []
    for comp in comps:
        for season in seasons:
            matches = provider.fetch_matches(comp, season)
            odds = provider.fetch_odds(comp, season)
            all_matches.append(matches)
            all_odds.append(odds)
            typer.echo(f"{comp} {season}: {len(matches)} matches, {len(odds)} odds rows")

    pd.concat(all_matches, ignore_index=True).to_parquet(out_dir / "matches.parquet")
    pd.concat(all_odds, ignore_index=True).to_parquet(out_dir / "odds.parquet")
    typer.echo(f"wrote {out_dir}/matches.parquet + odds.parquet")


if __name__ == "__main__":
    app()
