"""Export static JSON for the dashboard into site/public/data/ (no server — Pages-ready).

Writes three files the React app reads directly:
  - tips.json      : shadow-mode WM tips (goals-only market board, no odds)
  - backtest.json  : the honest-harness story (yield-CI, CLV beat-rate, verdict, bankroll curve)
  - meta.json      : generation timestamp + the disclaimer

Derived artifacts only (my computed tips/results) — never raw source data — so they are safe to
commit and to serve. Run: uv run python scripts/export_site.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from matchscout.backtest.engine import settle_bets
from matchscout.backtest.metrics import summary, verdict
from matchscout.config import load_env
from matchscout.data.football_data_co_uk import FootballDataCoUk
from matchscout.data.football_data_org import FootballDataOrg
from matchscout.evaluation.walk_forward import walk_forward_predict
from matchscout.tips import fixture_tips, suggest_combo
from matchscout.value.edge import select_value_bets

CACHE = Path(".cache")
OUT = Path("site/public/data")

DISCLAIMER = (
    "Educational simulation, paper stakes only — not gambling advice. "
    "Live tips are shadow-mode (no odds, no stake) and can be overconfident on thin data. "
    "The backtest is the honest measurement: the model does not beat the closing line."
)


# Competitions to check for live fixtures, in display order. Whatever has scheduled fixtures
# right now shows up — World Cup today, the leagues once their season kicks off. No hardcoding.
LIVE_COMPS = [
    ("WC", "World Cup", "cup"),
    ("CL", "Champions League", "cup"),
    ("EC", "European Championship", "cup"),
    ("PL", "Premier League", "league"),
    ("BL1", "Bundesliga", "league"),
    ("SA", "Serie A", "league"),
    ("PD", "La Liga", "league"),
    ("FL1", "Ligue 1", "league"),
]


def _upcoming(season: str = "2026") -> dict:
    provider = FootballDataOrg(CACHE)
    now = pd.Timestamp.now(tz="UTC")
    groups = []
    for code, name, kind in LIVE_COMPS:
        try:
            matches = provider.fetch_matches(code, season, refresh=True)
        except Exception:
            continue  # off-season / season not yet available -> skip
        played = matches[matches["status"] == "played"]
        scheduled = matches[matches["status"] == "scheduled"]
        if played.empty or scheduled.empty:
            continue
        try:
            tips = fixture_tips(played, scheduled, as_of=now)
        except Exception:
            continue  # too few played matches to fit yet (early season)
        if tips.empty:
            continue
        tips = tips.copy()
        tips["date"] = tips["date"].astype(str)
        groups.append(
            {
                "code": code,
                "name": name,
                "kind": kind,
                "n_scheduled": int(len(scheduled)),
                "n_trained_on": int(len(played)),
                "tips": tips.to_dict(orient="records"),
                "combo": suggest_combo(tips, n_legs=3),
            }
        )
    return {"generated_at": now.isoformat(), "season": season, "competitions": groups}


TOP5 = ["E0", "SP1", "D1", "I1", "F1"]
LEAGUE_NAMES = {
    "E0": "Premier League",
    "SP1": "La Liga",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "F1": "Ligue 1",
}


def _backtest(seasons=("2223", "2324")) -> dict:
    provider = FootballDataCoUk(CACHE)
    matches = pd.concat(
        [provider.fetch_matches(c, s) for c in TOP5 for s in seasons], ignore_index=True
    )
    odds = pd.concat(
        [provider.fetch_odds(c, s) for c in TOP5 for s in seasons], ignore_index=True
    )
    preds = walk_forward_predict(matches, min_train=80, half_life_days=180.0)
    picks = select_value_bets(preds, odds, threshold=0.05, book="B365")
    comp_of = dict(zip(matches["match_id"], matches["competition"], strict=False))

    schemes = {}
    for name in ("flat", "kelly"):
        ledger = settle_bets(
            picks, matches, odds, staking=name, flat_unit=10.0, start_bankroll=1000.0
        )
        summ = summary(ledger)
        # Cumulative profit (net units from break-even), not "bankroll": a fixed flat stake is not
        # bankroll-constrained, so a bankroll axis would dip below zero. Profit-from-0 is honest.
        curve = [
            {"date": str(r.date)[:10], "profit": round(float(r.bankroll_after) - 1000.0, 2)}
            for r in ledger.sort_values("date").itertuples()
        ]
        schemes[name] = {"summary": summ, "curve": curve, "verdict": verdict(summ)}

    # Per-league breakdown: settle each league's bets on its own flat bankroll.
    per_league = []
    for comp in TOP5:
        league_picks = picks[picks["match_id"].map(comp_of) == comp]
        ls = summary(settle_bets(league_picks, matches, odds, staking="flat", flat_unit=10.0))
        per_league.append(
            {
                "league": LEAGUE_NAMES[comp],
                "n_bets": ls.get("n_bets", 0),
                "yield": ls.get("yield"),
                "clv_beat_rate": ls.get("clv_beat_rate"),
                "final_bankroll": ls.get("final_bankroll"),
            }
        )

    flat = schemes["flat"]["summary"]
    dates = [p["date"] for p in schemes["flat"]["curve"]]
    return {
        "competitions": [LEAGUE_NAMES[c] for c in TOP5],
        "seasons": list(seasons),
        "start_bankroll": 1000.0,
        "date_range": [dates[0], dates[-1]] if dates else [],
        "clv_beat_rate": flat["clv_beat_rate"],
        "clv_mean": flat["clv_mean"],
        "headline_verdict": schemes["flat"]["verdict"],
        "schemes": schemes,
        "per_league": per_league,
    }


def main() -> None:
    load_env()
    OUT.mkdir(parents=True, exist_ok=True)

    try:
        upcoming = _upcoming()
    except Exception as exc:  # no key etc. — write an empty-but-valid file
        upcoming = {"competitions": [], "error": str(exc)[:120]}
    (OUT / "upcoming.json").write_text(json.dumps(upcoming, indent=2))
    print(f"upcoming.json: {len(upcoming.get('competitions', []))} competitions with fixtures")

    backtest = _backtest()
    (OUT / "backtest.json").write_text(json.dumps(backtest, indent=2))
    print(f"backtest.json: {backtest['schemes']['flat']['summary']['n_bets']} bets, 2 schemes")

    meta = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "disclaimer": DISCLAIMER}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {OUT}/")


if __name__ == "__main__":
    main()
