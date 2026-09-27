"""D7: measure pre-match vs. closing price movement over the cached Top-5 seasons.

    uv run python scripts/analyze_odds_gap.py                       # default seasons
    uv run python scripts/analyze_odds_gap.py --seasons 2223 --seasons 2324

Writes `data/odds_gap_report.json` (derived numbers only — the raw CSVs stay in `.cache/`).
See `matchscout.evaluation.odds_gap` for the method and the weak/informative rule.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from matchscout.data.football_data_co_uk import FootballDataCoUk
from matchscout.evaluation.odds_gap import WEAK_MEDIAN_PP, findings, gap_report, price_gaps

app = typer.Typer(add_completion=False)
CACHE = Path(".cache")
TOP5 = ["E0", "SP1", "D1", "I1", "F1"]


@app.command()
def main(
    seasons: Annotated[list[str] | None, typer.Option()] = None,
    out: Annotated[Path, typer.Option()] = Path("data/odds_gap_report.json"),
) -> None:
    seasons = seasons or ["2223", "2324", "2526", "2627"]
    provider = FootballDataCoUk(CACHE)
    matches = pd.concat(
        [provider.fetch_matches(c, s) for c in TOP5 for s in seasons], ignore_index=True
    )
    odds = pd.concat([provider.fetch_odds(c, s) for c in TOP5 for s in seasons], ignore_index=True)
    gaps = price_gaps(odds, dict(zip(matches["match_id"], matches["competition"], strict=False)))
    gaps["season"] = gaps["match_id"].str.split(":").str[1]

    pooled = gap_report(gaps, ["market", "reference"])
    report = {
        "method": (
            "Shin de-vigged probability gap p_close(reference) - p_pre(B365) per selection; "
            f"a segment is 'weak' if its median |gap| < {WEAK_MEDIAN_PP * 100:.1f} pp"
        ),
        "seasons": seasons,
        "competitions": TOP5,
        "n_matches": int(gaps["match_id"].nunique()),
        "pooled": pooled,
        "per_season": gap_report(gaps, ["season", "market", "reference"]),
        "per_league": gap_report(gaps, ["competition", "market", "reference"]),
        "findings": findings(pooled),
    }
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for line in report["findings"]:
        typer.echo(line)
    typer.echo(f"wrote {out} ({report['n_matches']} matches)")


if __name__ == "__main__":
    app()
