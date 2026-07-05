"""Ingest CL / WC / EC fixtures + results into canonical Parquet (matches only, no odds).

These competitions have no free odds, so they are shadow-mode: the model can predict them but
no bets are staked. Loads the football-data.org key from .env.

    uv run python scripts/ingest_org.py --competitions CL --seasons 2024
    uv run python scripts/ingest_org.py --competitions WC --seasons 2026
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.config import load_env
from matchscout.data.football_data_org import FootballDataOrg

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")


@app.command()
def main(
    competitions: Annotated[list[str], typer.Option(help="CL, WC, and/or EC.")],
    seasons: Annotated[list[str], typer.Option(help="Start year, e.g. 2024 or 2026.")],
) -> None:
    load_env()
    provider = FootballDataOrg(CACHE)
    out_dir = CACHE / "canonical_org"
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for comp in competitions:
        for season in seasons:
            try:
                matches = provider.fetch_matches(comp, season)
            except Exception as exc:  # season not available / off-season / rate-limit — skip
                typer.echo(f"{comp} {season}: skipped ({type(exc).__name__}: {str(exc)[:80]})")
                continue
            frames.append(matches)
            played = int((matches["status"] == "played").sum())
            typer.echo(f"{comp} {season}: {len(matches)} matches ({played} played)")

    if not frames:
        typer.echo("no competitions ingested")
        raise typer.Exit(1)
    pd.concat(frames, ignore_index=True).to_parquet(out_dir / "matches.parquet")
    typer.echo(f"wrote {out_dir}/matches.parquet")


if __name__ == "__main__":
    app()
