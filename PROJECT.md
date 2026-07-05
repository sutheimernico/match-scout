# match-scout — Project (Source of Truth)

**Stand:** 2026-07-05 · **Status:** scaffold on `autopilot/work`, gate green
(`uv run pytest -q` + `uv run ruff check .`); Phase 1 (data layer) next.
Personal rules (`~/.claude/CLAUDE.md`) + global loop rules (`~/private/AUTOPILOT.md`) apply.
Design depth: `docs/superpowers/specs/2026-07-05-match-scout-design.md`. Working method: below.
Latest iteration log: `AUTOPILOT_LOG.md`.

---

# Part I — Specification

## 1 · Vision & non-negotiables

Honest measurement harness for football prediction + betting-slip simulation — **not a tipster, no
edge promise.** The deliverable is the rigorous, self-operating pipeline that tracks whether a
systematic model would have been profitable against real bookmaker **closing odds, after the vig**.
A slightly negative ROI is the likely honest outcome and would be reported, not hidden. Local &
free, paper stakes only, disclaimer on every surface, point-in-time integrity, benchmark-first.

## 2 · Architektur

`data/ (seam + cache)` → `model/ (Dixon-Coles, Elo)` → `value/ (edge vs vig-adjusted odds,
selection, Wettschein)` → `backtest/ (walk-forward sim, bankroll, staking, metrics, baselines)` +
`forward/ (idempotent paper loop, ledger)` + `ml/ (LightGBM challenger)` → `api/` → `site/`. See
spec §2 for the diagram. One responsibility per module; providers behind a seam with fakes; no live
network in tests.

## 3 · Scope

**Drin:** Top-5 leagues (E0/SP1/D1/I1/F1) as the betting universe with real P&L; markets **1X2 +
Over/Under 2.5**; Dixon-Coles + Elo + LightGBM-challenger; historical backtest + idempotent forward
loop with flat + 0.25-Kelly staking; CL + WM as predictions in **shadow-mode** (no odds → no stake).

**Draußen:** BTTS (no free odds), Asian Handicap (deferred), player-level features
(injuries/lineups/form — needs rate-limited paid-ish API, deferred layer), DFB-Pokal (no free
data), real-money / in-play (never).

## 4 · Datenmodell

Canonical tables: `matches`, `odds` (with `is_closing`), `predictions`, `bets` (ledger),
`bankroll_snapshots`. Full field lists in spec §4. `timestamp_event` (kickoff) is audit-only; only
`timestamp_known` selects/prices a bet.

## 5 · Tech-Stack

Python ≥3.11, uv, pytest + ruff (`E/F/I/UP/B/SIM`, line-length 100). pandas/numpy/pyarrow/httpx/typer
core; scipy @ Phase 2; lightgbm @ Phase 5; fastapi @ API phase. React 19 + Vite + hand-rolled SVG
charts. GitHub Actions cron + Pages + Issues; git-scraping of derived artifacts only.

## 6 · Acceptance criteria

See spec §8 (1–6). Headline metric = margin vs. the closing-line baseline; rule-generated verdict;
green gate; no committed raw CSVs; disclaimer everywhere.

---

# Part II — Plan & working method

## Roadmap

Phases live in `PLAN.md` (the binding autopilot backlog). Summary: **0** scaffold ✅ · **1** data
layer · **2** goal model (Dixon-Coles + Elo) · **3** value & selection · **4** backtest engine
(first real run) · **5** ML challenger · **6** forward paper loop · **7** GitHub Actions pipeline ·
**8** dashboard · **9** publish.

## Working method

Superpowers flow for non-trivial work; per-iteration protocol from `LOOP.md`; gate = `uv run
pytest -q` green + `uv run ruff check .` clean, commit only green, on `autopilot/work`. Once per
phase: SOTA self-challenge → ADR under `docs/adr/`.

## §Decisions (register — closed, dated)

- **2026-07-05** Framing: **honest measurement harness, no edge promise** (signal-trader DNA).
- **2026-07-05** Data: **football-data.co.uk** (free historical results + odds, Top-5) +
  **football-data.org free tier** (fixtures, CL/WM, no odds). Raw CSVs **not committed** (license
  "for match prediction only").
- **2026-07-05** Scope: **Top-5 betting universe**; **CL/WM shadow-mode** (predictions, no stake);
  **DFB-Pokal parked** (no free data).
- **2026-07-05** Markets: **1X2 + Over/Under 2.5**. **BTTS dropped** (no free odds); **Asian
  Handicap deferred**.
- **2026-07-05** Model: **Dixon-Coles** workhorse + **Elo** baseline; **LightGBM** as a walled-off
  challenger that must beat Dixon-Coles AND the closing line to count.
- **2026-07-05** Staking: **flat 1u + 0.25-Kelly**, start bankroll **1000u**, two paper accounts.
- **2026-07-05** Backtest closing-odds window **2019/20+**; older seasons use pre-match odds, labeled.
- **2026-07-05** Benchmark: **closing-line-implied prob (after vig)** + naive baselines
  (always-home/favorite/over-2.5).
- **2026-07-05** Ops: **GitHub Actions cron + git-scraping** (derived artifacts only) + Pages
  dashboard; `main` left unborn until Nico's first review/merge.

## §Open inputs (living — external facts Nico owns → "Needs Nico")

- [ ] Git remote + visibility (public repo under `sutheimernico/match-scout`?) before any first push.
- [x] football-data.org **free API key** — PROVIDED 2026-07-05 (stored in `.env`, gitignored;
      live-verified against WC 2026 + CL 2024/25). Still needs adding as a GitHub Actions repo secret
      `FOOTBALL_DATA_API_KEY` when the remote is set up.
- [ ] Optional later: **The Odds API** key to enable real *forward* CL/WM P&L (free tier = live
      odds only; historical is paid). Not a blocker.
- [ ] Merges to `main`: Nico reviews `autopilot/work` and merges.
