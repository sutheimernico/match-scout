# match-scout

**An honest measurement harness for football match prediction and betting-slip simulation — not a tipster, no edge promise.**

> ⚠️ **Educational simulation, paper stakes only. This is not gambling advice and not a betting
> product.** No real money is ever staked. Beating bookmaker closing odds after the margin is
> extremely hard; a slightly negative ROI is the expected honest outcome — and if the model does
> not beat the closing-line baseline, that is the reported finding, not something hidden.

match-scout ingests free historical results and bookmaker odds for the Top-5 European leagues,
fits a statistical goal model (Dixon-Coles) plus a walled-off ML challenger, finds bets where the
model disagrees with the market in its favour, and simulates a bankroll over time — measured
against the market's own closing line and naive baselines, after the vig. A forward paper loop
records predictions and paper bets **before kickoff** and settles them afterwards, so the live
record cannot be hindsight.

## Status — what is built and what it found

- [x] **Phase 0 — Scaffold** (uv + ruff + pytest gate, docs, methodology reviewer).
- [x] **Phase 1 — Data layer.** football-data.co.uk (results + odds, key-free) and
      football-data.org (fixtures, free key). The running season is refetched on every forward run.
- [x] **Phase 2 — Goal model.** Dixon-Coles with time decay. **Does not beat the closing line:**
      Brier 0.570 vs. market 0.547 (Premier League 2022/23–2023/24, walk-forward).
- [x] **Phase 3 — Value & selection.** Edge on the Bet365 pre-match price; Shin de-vig for the
      benchmark only. (Accumulator demo still open.)
- [x] **Phase 4 — Backtest.** Top-5, 2022/23–2023/24: **4,540 paper bets, flat yield −8.8 %,
      95 % CI [−12.8 %, −4.8 %] — a statistically significant loss**; only 22 % of bets beat the
      closing line. Every league loses.
- [x] **Phase 5 — ML challenger.** LightGBM beats **neither** Dixon-Coles nor the market (overfits
      the small sample).
- [x] **Phase 6 — Forward paper loop.** Running since 2026-09-20. First settled run: 12 paper bets,
      1 won, −105 units, 0 of 12 beat the (market-average) closing line — far too few for any
      verdict; the page says so.
- [~] **Phase 7 — CI.** `ci.yml` + `pipeline.yml` authored; **inert until the repo has a remote**.
      Until then the loop runs from a local cron (below).
- [x] **Phase 8 — Dashboard.** React dashboard (backtest story + live paper-record panel) and the
      German **Spieltag** page.
- [ ] **Phase 9 — Publish** (Needs Nico: remote, visibility, publish checklist).

## Honest harness (what makes the numbers trustworthy)

- **Benchmark-first:** every strategy is measured against the closing-line-implied probability
  (the market, after vig) and naive baselines (always-home / always-favourite / always-over-2.5).
- **Point-in-time integrity, enforced twice:** the schema rejects any odds row with
  `timestamp_known > timestamp_event`, and `fit_dixon_coles` takes a required `as_of` and raises on
  any training row on or after it. A behavioural no-lookahead test covers the walk-forward.
- **Vig removed before any edge claim;** P&L settles at real (with-vig) odds.
- **Leak detection:** a market-null / placebo test (ADR 0002) — the real result sits inside the
  null distribution, i.e. no edge and no leak.
- **Multiple-trials honesty (D1, ADR 0003):** every configuration ever run is appended to
  `data/trial_log.jsonl`; a Deflated-Sharpe hurdle raises the bar with every logged trial.
- **Is CLV a meaningful yardstick? (D7, measured):** over 5,580 Top-5 matches the de-vigged gap
  between the Bet365 pre-match price and the close has a median of 1.2–1.3 pp (1X2) and
  1.8–2.1 pp (O/U 2.5); 57–74 % of prices move ≥ 1 pp. No segment is "weak", so beating the close
  carries information everywhere we bet (`data/odds_gap_report.json`).

## Jeden Spieltag — how to use it each matchday

**What runs by itself.** A local cron entry runs `scripts/run_matchday.sh` at **08:47 and 17:47**
(German time) every day: it fetches the fixtures feed and the running season, logs a prediction
for every priced Top-5 fixture (`data/predictions.jsonl`), places paper bets where the model's
edge is ≥ 5 % (`data/bets.jsonl`), settles everything that has been played, and rebuilds the
pages. Re-running is a no-op, so a missed or doubled run does no harm. Log: `logs/forward.log`.

**What to open.** The German matchday page `site/public/spieltag.html` — next fixtures per league
with model vs. market probabilities, open paper bets, settled bets with CLV, and the running record
with n and confidence intervals:

```bash
explorer.exe "$(wslpath -w site/public/spieltag.html)"   # from WSL
npm --prefix site run dev   # or via the dashboard: <printed URL>/spieltag.html
```

During an international break the page says there are no Top-5 fixtures; they appear once
football-data.co.uk publishes the matchday's prices (usually Tuesday / Friday afternoon).

**Now and then: commit the record.** The cron never commits (it must not write to whatever branch
is checked out). Commit the derived artifacts yourself:

```bash
git add data/bets.jsonl data/predictions.jsonl data/bankroll_snapshots.jsonl \
        site/public/spieltag.html site/public/data/forward.json
git commit -m "chore(data): forward runs up to $(date +%F)"
```

**Run it by hand:** `./scripts/run_matchday.sh` (or the two steps:
`uv run python scripts/run_forward.py` then `uv run python scripts/spieltag.py`).

**Stop the schedule** (removes only the match-scout lines; a backup of the crontab as it was
before is in `logs/crontab.backup-2026-09-27`):

```bash
crontab -l | grep -v 'match-scout' | crontab -
```

Remove it before activating `pipeline.yml` on a remote — the ledger must have exactly one writer.
The cron needs `feat/forward-proof` (or a branch containing it) checked out.

## Run it yourself

```bash
uv sync
uv run pytest && uv run ruff check .                 # gate
uv run python scripts/ingest.py --help               # canonical tables from the cache
uv run python scripts/run_backtest.py --help         # walk-forward backtest (logs a trial)
uv run python scripts/analyze_odds_gap.py            # D7 report
uv run python scripts/export_site.py                 # dashboard JSON
npm --prefix site run build                          # dashboard (tsc strict + vite)
```

## Scope

Betting universe: Top-5 leagues (England, Spain, Germany, Italy, France), markets 1X2 + Over/Under
2.5. Champions League + World Cup: predictions in shadow-mode (no free odds → no stake).
Player-level features (injuries/lineups/form) and DFB-Pokal are out of v1 — see `PROJECT.md`.

## Stack

Python 3.11+ · uv · pandas / numpy / scipy · Dixon-Coles + LightGBM · React 19 + Vite (dashboard) ·
GitHub Actions (authored, inert until a remote exists).

Data: results & odds from [football-data.co.uk](https://www.football-data.co.uk/) (used for match
prediction per their stated terms; raw files are not redistributed here), fixtures from
[football-data.org](https://www.football-data.org/) (free tier). Code: MIT.
