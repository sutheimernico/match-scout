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
    "World Cup tips are shadow-mode (no odds, no stake) and overconfident on thin data. "
    "The league backtest is the honest measurement: the model does not beat the closing line."
)


def _wm_tips() -> dict:
    provider = FootballDataOrg(CACHE)
    matches = provider.fetch_matches("WC", "2026")
    played = matches[matches["status"] == "played"]
    scheduled = matches[matches["status"] == "scheduled"]
    tips = fixture_tips(played, scheduled, as_of=pd.Timestamp.now(tz="UTC"))
    combo = suggest_combo(tips, n_legs=3)
    tips = tips.copy()
    if not tips.empty:
        tips["date"] = tips["date"].astype(str)
    return {
        "competition": "FIFA World Cup 2026",
        "n_trained_on": int(len(played)),
        "tips": tips.to_dict(orient="records"),
        "combo": combo,
    }


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
        tips = _wm_tips()
    except Exception as exc:  # no key / off-tournament — write an empty-but-valid file
        tips = {"competition": "FIFA World Cup 2026", "tips": [], "error": str(exc)[:120]}
    (OUT / "tips.json").write_text(json.dumps(tips, indent=2))
    print(f"tips.json: {len(tips.get('tips', []))} tips")

    backtest = _backtest()
    (OUT / "backtest.json").write_text(json.dumps(backtest, indent=2))
    print(f"backtest.json: {backtest['schemes']['flat']['summary']['n_bets']} bets, 2 schemes")

    meta = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "disclaimer": DISCLAIMER}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {OUT}/")


if __name__ == "__main__":
    main()
