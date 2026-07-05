"""Shadow-mode tips for a competition without free odds (Champions League, World Cup).

    uv run python scripts/tips.py --competition WC --seasons 2026
    uv run python scripts/tips.py --competition CL --seasons 2024

Fits Dixon-Coles on the PLAYED matches from football-data.org and prints tips for the SCHEDULED
fixtures. No odds -> shadow-mode: predictions only, never a stake. Off-season competitions have no
scheduled fixtures, so there is nothing to tip until the next draw/season.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.config import load_env
from matchscout.data.football_data_org import FootballDataOrg
from matchscout.tips import fixture_tips, suggest_combo

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")


@app.command()
def main(
    competition: Annotated[str, typer.Option(help="CL, WC, or EC.")],
    seasons: Annotated[list[str], typer.Option(help="Start year(s) to train on.")],
    half_life_days: Annotated[float, typer.Option()] = 365.0,
) -> None:
    load_env()
    provider = FootballDataOrg(CACHE)
    frames = []
    for season in seasons:
        try:
            frames.append(provider.fetch_matches(competition, season))
        except Exception as exc:
            typer.echo(f"{competition} {season}: skipped ({type(exc).__name__}: {str(exc)[:70]})")
    if not frames:
        raise typer.Exit(1)

    everything = pd.concat(frames, ignore_index=True)
    played = everything[everything["status"] == "played"]
    scheduled = everything[everything["status"] == "scheduled"]
    typer.echo(
        f"{competition}: trained on {len(played)} played; {len(scheduled)} scheduled fixtures"
    )

    tips = fixture_tips(
        played, scheduled, half_life_days=half_life_days, as_of=pd.Timestamp.now(tz="UTC")
    )
    if tips.empty:
        typer.echo("no tips — no scheduled fixtures with known teams (off-season?). SHADOW-MODE.")
        return

    typer.echo("\nSHADOW-MODE TIPS — goals-only markets, no odds, no stake.")
    typer.echo("(Goalscorer/card/corner markets need player/event data the free stack lacks.)\n")
    for r in tips.sort_values("date").itertuples():
        typer.echo(f"{str(r.date)[:16]}  {r.home} vs {r.away}")
        typer.echo(
            f"   1X2: {r.tip_1x2}  (H {r.p_H:.0%}/D {r.p_D:.0%}/A {r.p_A:.0%})   "
            f"advance(KO): {r.home} {r.p_home_adv:.0%} / {r.away} {r.p_away_adv:.0%}"
        )
        typer.echo(
            f"   O/U: >0.5 {r.p_over05:.0%} · >1.5 {r.p_over15:.0%} · "
            f">2.5 {r.p_over25:.0%} · >3.5 {r.p_over35:.0%}   BTTS {r.p_btts:.0%}"
        )
        typer.echo(f"   likely {r.most_likely_score}   top: {r.top_scores}")

    combo = suggest_combo(tips, n_legs=3)
    if combo["n_legs"]:
        legs = " + ".join(f"{leg['match']} [{leg['pick']} {leg['p']:.0%}]" for leg in combo["legs"])
        typer.echo(
            f"\nCOMBO (illustrative only — accumulators are −EV): {legs}  "
            f"→  combined model prob {combo['combined_prob']:.1%}"
        )


if __name__ == "__main__":
    app()
