# match-scout — Design (Spec)

**Stand:** 2026-07-05 · **Status:** Design locked, scaffold on `autopilot/work`, Phase 1 next.
Personal rules (`~/.claude/CLAUDE.md`) + global loop rules (`~/private/AUTOPILOT.md`) apply.

---

## 1. Vision & non-negotiables

An **honest measurement harness** for football match prediction and betting-slip simulation —
**not a tipster, no profit promise.** Same DNA as `signal-trader-demo`: the product is the
rigorous, self-operating pipeline that transparently tracks whether a systematic model would have
been profitable **against real bookmaker closing odds, after the margin (vig)**.

The honest expectation, stated up front: beating closing odds is extremely hard; a slightly
negative ROI is the likely outcome. The portfolio value is the methodology and the live pipeline,
not the profit. If the model does not beat the closing-line baseline, **that is the reported
finding**, not a failure to hide.

Non-negotiables:

- **Local & free.** Only free data (football-data.co.uk, football-data.org free tier). No paid
  feeds. No real money — paper stakes only, always.
- **Honesty guardrails on every surface.** A loud "educational simulation, paper-stakes only, not
  gambling advice" disclaimer on the README, the dashboard, and every report.
- **Point-in-time integrity.** A bet is only ever placed on information knowable *before* kickoff.
- **Benchmark-first.** Every strategy is measured against the closing-line-implied probability
  (the market, after vig) and naive baselines — never accuracy alone.

## 2. Architecture

```
football-data.co.uk CSVs ─┐                 (results + bookmaker odds, Top-5 leagues)
football-data.org API ────┤─▶ data/ (seam + cache) ─▶ model/ (Dixon-Coles, Elo)
  (fixtures, CL/WM)        │                                    │
                          fakes (tests)                         ▼
                                                        value/ (edge vs vig-adjusted odds,
                                                                selection, Wettschein)
                                                                │
                                          ┌─────────────────────┼───────────────────────┐
                                          ▼                     ▼                       ▼
                                   backtest/ (walk-      forward/ (idempotent      ml/ (LightGBM
                                   forward sim,          paper loop, ledger,       challenger,
                                   bankroll, staking,    ROI snapshots)            purged WF,
                                   metrics, baselines)          │                  must beat both)
                                          │                     │
                                          └────────▶ api/ (FastAPI read) ─▶ site/ (React dashboard)
                                                     GitHub Actions cron + git-scraping + Pages
```

One responsibility per module. Data providers sit behind a seam with fakes; **no live network in
tests**.

## 3. Scope

**Drin (v1):**
- **Betting universe (real P&L):** Top-5 domestic leagues — England (E0), Spain (SP1), Germany
  (D1), Italy (I1), France (F1). These have free historical results + bookmaker odds.
- **Markets:** 1X2 (home/draw/away) and Over/Under 2.5 goals. Both have free odds columns.
- **Model:** Dixon-Coles (bivariate Poisson + low-score correction + time-decay) as the workhorse;
  Elo/attack-defence as an even simpler baseline; LightGBM as a walled-off ML challenger.
- **Simulation:** historical walk-forward backtest **and** a stateful, idempotent forward paper
  loop, both accumulating a bankroll over time with flat and fractional-Kelly staking.
- **CL + World Cup:** fixtures/results ingested (football-data.org free tier), feed the
  cross-competition ratings, and the model **produces predictions** — but bets run in
  **shadow-mode** (probabilities logged, no stake) because no free odds exist for them.

**Draußen (v1) — YAGNI / data-limited:**
- **BTTS (both-teams-to-score) market** — football-data.co.uk has no BTTS odds.
- **Asian Handicap market** — odds exist; deferred as a post-v1 market extension.
- **Player-level features** (injuries, lineups, form, returning players) — needs the rate-limited
  rich API (API-Football, ~100 req/day). Deferred as a separate feature layer once the harness
  stands. This is the biggest deferral vs. the original ask and is intentional.
- **DFB-Pokal betting** — no free fixtures (not on football-data.org free tier) and no free odds.
  Parked entirely.
- **Real-money / in-play / live betting** — never.

## 4. Data model

Canonical, source-agnostic tables (persisted as Parquet in cache, derived artifacts in `data/`):

- **`matches`**: `match_id, competition, season, date, kickoff_utc, home, away, ft_home_goals,
  ft_away_goals, status` (scheduled | played | void). `timestamp_event` = kickoff;
  `timestamp_known` = when the row (and its odds) became knowable.
- **`odds`**: `match_id, market (1x2|ou25), selection (H|D|A|over|under), book, odds, is_closing,
  collected_at`. Closing (`C`) columns → `is_closing=true` (available ~2019/20+); pre-match `Avg*`
  → `is_closing=false`. Market aggregate `Avg`/`Max` kept alongside individual books.
- **`predictions`**: `match_id, model, market, selection, p_model, fair_odds, generated_at`.
- **`bets`** (ledger): `bet_id, match_id, market, selection, model, stake_scheme (flat|kelly),
  stake, odds_taken, is_closing_odds, placed_at (=timestamp_known), settled_at, result
  (win|loss|void|open), pnl, bankroll_after`.
- **`bankroll_snapshots`**: `date, stake_scheme, bankroll, turnover, n_bets, roi, yield`.

## 5. Tech-Stack

Python ≥3.11, **uv** (pinned `pyproject.toml` + `uv.lock`), **pytest** + **ruff** (line-length 100,
select `E/F/I/UP/B/SIM`). Core libs: pandas, numpy, pyarrow (Parquet cache), httpx (fetch), typer
(CLI); scipy (Dixon-Coles MLE) added at Phase 2; lightgbm at Phase 5; fastapi at the API phase.
Dashboard: React 19 + Vite + TS with hand-rolled SVG charts (grid-scout pattern). Ops: GitHub
Actions cron + Pages + Issues; git-scraping of derived artifacts only.

## 6. Honesty & anti-overfit methodology

- **Point-in-time / timestamp discipline:** only `timestamp_known` selects or prices a bet;
  `timestamp_event` is audit-only.
- **Closing-line correctness:** bets are *placed* at pre-match odds (knowable) and closing odds are
  used to measure **CLV** and to settle honestly — never priced as if closing odds were available
  at placement time.
- **Vig removed before any edge claim:** `edge = p_model * odds - 1`, compared against the
  margin-adjusted implied probability; P&L settled at real (with-vig) odds.
- **Shift-test:** lag all inputs one matchday and re-run; a real edge survives, a leak collapses.
- **Purged + embargoed walk-forward** for the ML challenger; a rising significance hurdle
  (Deflated-Sharpe / PBO analog for ROI) + a logged trial count so a wide search can't win by luck.
- **Baselines always:** always-home, always-favorite, always-over-2.5, and the closing-line-implied
  probability (the market benchmark, after vig).
- **Metrics:** calibration (Brier, log-loss, reliability curve), yield (profit/turnover), max
  drawdown, ROI, CLV — never accuracy or ROI alone.
- **`betting-methodology-reviewer` subagent** (read-only, sonnet) runs after any change to
  `value/`, `backtest/`, `forward/`, `model/`, `ml/` and whenever a result "looks profitable".

## 7. Data-source facts (verified 2026-07-05)

- **football-data.co.uk** — per-season/per-league CSVs at
  `https://www.football-data.co.uk/mmz4281/{SEASON}/{DIV}.csv` (`SEASON` e.g. `2526`; `DIV` e.g.
  `E0`, `SP1`, `D1`, `I1`, `F1`). Odds: 1X2 (`B365H/D/A`, `PSH/D/A`, `AvgH/D/A`, `MaxH/D/A`), O/U 2.5
  (`B365>2.5`/`<2.5`, `Avg>2.5`), Asian Handicap (`AHh`, `B365AHH/AHA`, …). **Closing** odds via `C`
  suffix (`B365CH`, `AvgCH`, `AvgC>2.5`), present ~2019/20+. Results back to 1993/94, odds back to
  2000/01. **No BTTS odds. No cups/CL/WM.** License: *"for league match prediction only"* — no
  redistribution grant → **fetch at runtime, keep raw CSVs out of git, credit the source.**
- **football-data.org (API v4)** — free tier covers 12 competitions incl. Champions League, World
  Cup, European Championship, and the Top-5 leagues; **DFB-Pokal is NOT on the free tier.** Rate
  limit **10 req/min**. **No odds anywhere.** Auth: `X-Auth-Token` header (free key → Needs Nico;
  only used for CL/WM fixtures + as a fixtures fallback).
- **The Odds API** — 500 credits/month free, live/upcoming odds only (**historical odds are
  paid**). Covers CL/WM h2h/totals/spreads. Documented upgrade path for *forward* CL/WM P&L; not
  usable for historical CL/WM backtesting on the free tier.

## 8. Acceptance criteria

1. A one-command historical backtest over the Top-5 leagues (closing-odds window 2019/20+) produces
   a bankroll curve, ROI/yield, drawdown, calibration curve, and CLV — for flat and 0.25-Kelly
   staking — measured against the closing-line and naive baselines. Every number is computed, never
   estimated.
2. The reported headline is the **margin vs. the closing-line baseline**; if the model does not
   beat it, the report says so in a rule-generated verdict.
3. A stateful, idempotent forward paper loop advances one matchday at a time, logs bets at
   `timestamp_known`, settles from real results, and snapshots the bankroll — safe to run repeatedly
   (running twice on the same date is a no-op).
4. The ML challenger reports an honest scorecard (Brier, log-loss, ROI vs. Dixon-Coles + closing
   line, shift-test) and only "counts" if it beats both baselines out-of-sample.
5. `uv run pytest` green + `uv run ruff check .` clean; no live network in tests.
6. Every output surface carries the disclaimer; raw source CSVs are never committed.

## 9. Open questions to verify during build

- **Forward odds for upcoming matches:** does the current-season football-data.co.uk CSV include
  unplayed fixtures with pre-match odds a few days ahead? (Notes say odds are collected Friday for
  weekend games → likely yes.) Verify in Phase 6; if not, fall back to football-data.org fixtures
  (no odds → shadow-mode) for those matches.
- **Void/postponed handling** in the settled-bet sample (stake returned, excluded from yield).
- **Kelly variance:** confirm 0.25-Kelly on a noisy edge does not blow up the bankroll; cap per-bet
  stake as a guard.
