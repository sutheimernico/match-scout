# match-scout

**An honest measurement harness for football match prediction and betting-slip simulation — not a tipster, no edge promise.**

> ⚠️ **Educational simulation, paper stakes only. This is not gambling advice and not a betting
> product.** No real money is ever staked. Beating bookmaker closing odds after the margin is
> extremely hard; a slightly negative ROI is the expected honest outcome — and if the model does
> not beat the closing-line baseline, that is the reported finding, not something hidden.

match-scout ingests free historical results and bookmaker odds for the Top-5 European leagues,
fits a statistical goal model (Dixon-Coles) plus a walled-off ML challenger, finds bets where the
model disagrees with the market in its favour, and simulates a bankroll over time — measured
against the market's own closing line and naive baselines, after the vig. It runs itself for €0 on
GitHub Actions.

## Status

Early build (autopilot loop). See `PLAN.md` for the phase backlog and `AUTOPILOT_LOG.md` for the
iteration log.

- [x] Phase 0 — Scaffold (uv + ruff + pytest gate, docs, methodology-reviewer)
- [ ] Phase 1 — Data layer · Phase 2 — Goal model · Phase 3 — Value & selection ·
      Phase 4 — Backtest engine (first real run) · Phase 5 — ML challenger ·
      Phase 6 — Forward paper loop · Phase 7 — CI/pipeline · Phase 8 — Dashboard · Phase 9 — Publish

## Honest harness (what makes the numbers trustworthy)

- **Benchmark-first:** every strategy is measured against the closing-line-implied probability
  (the market, after vig) and naive baselines (always-home / always-favourite / always-over-2.5).
- **Point-in-time integrity:** a bet is priced only with odds knowable before kickoff; closing odds
  are used to measure closing-line value and to settle — never as the price you "got" earlier.
- **Vig removed before any edge claim;** P&L settles at real (with-vig) odds.
- **Leakage & overfitting guards:** shift-test, purged + embargoed walk-forward for ML, a rising
  significance hurdle, calibration (Brier / log-loss) — not accuracy or ROI alone.

## Scope

Betting universe: Top-5 leagues (England, Spain, Germany, Italy, France), markets 1X2 + Over/Under
2.5. Champions League + World Cup: predictions in shadow-mode (no free odds → no stake). Player-level
features (injuries/lineups/form) and DFB-Pokal are out of v1 — see `PROJECT.md`.

## Run it yourself

```bash
uv sync
uv run pytest -q          # gate
uv run ruff check .
# data ingestion / backtest CLIs land under scripts/ as phases complete
```

## Stack

Python 3.11+ · uv · pandas / numpy / scipy · Dixon-Coles + LightGBM · React 19 + Vite (dashboard) ·
GitHub Actions (cron + Pages + Issues).

Data: results & odds from [football-data.co.uk](https://www.football-data.co.uk/) (used for match
prediction per their stated terms; raw files are not redistributed here), fixtures from
[football-data.org](https://www.football-data.org/) (free tier). Code: MIT.
