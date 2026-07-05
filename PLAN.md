# match-scout — Plan (AUTOPILOT-driven build backlog)

**Source of truth for design:** `docs/superpowers/specs/2026-07-05-match-scout-design.md`
Personal rules (`~/.claude/CLAUDE.md`) + global loop rules (`~/private/AUTOPILOT.md`) apply.

This file is the binding backlog for the autonomous loop. Each iteration picks the SINGLE
highest-value open `- [ ]` task, does it on `autopilot/work`, runs the gate, commits only if green,
checks the box, and appends one line to `AUTOPILOT_LOG.md`.

## Iron principles (never overridden)

- **Local & free only.** football-data.co.uk + football-data.org free tier. No paid feeds, no real
  money. A task needing a paid resource or a Nico-only input goes to "Needs Nico", never faked.
- **Gate is objective:** `uv run pytest -q` green AND `uv run ruff check .` clean. Never commit red.
- **One change per iteration.** No bundling. No speculative abstractions (YAGNI).
- **Point-in-time integrity + vig honesty.** Only `timestamp_known` prices/selects a bet; edges are
  computed against margin-adjusted implied probs; P&L settles at real odds. No lookahead.
- **Raw source CSVs are never committed** (license). Only derived artifacts under `data/`.
- **New logic ships with a test.** No live network in tests — use fakes behind the provider seam.

## Status

- [x] **Phase 0 — Scaffold** — DONE 2026-07-05: uv + ruff + pytest gate green, LICENSE (MIT),
      `.gitignore` (raw CSVs excluded), `betting-methodology-reviewer` subagent, spec + PROJECT +
      PLAN + LOOP docs. Repo on `autopilot/work`, `main` unborn until Nico merges.

## Phase 1 — Data layer

Goal: canonical, source-agnostic match + odds tables from free sources, behind a seam with fakes.

- [ ] Provider seam: abstract `MatchDataProvider` + `OddsProvider` interfaces; `FakeProvider` with
      recorded fixtures for tests.
- [ ] football-data.co.uk fetcher: per-season/per-league CSV download (httpx, retry/backoff),
      column mapping → canonical `matches` + `odds` (1X2 + O/U2.5, individual books + Avg/Max,
      `is_closing` from `C` columns). Raw CSV → `.cache/` (gitignored).
- [ ] Read-through cache: Parquet under `.cache/`, freshness vs. injected run-date; skip complete
      past seasons, refresh current season.
- [ ] Canonical schema + validation (`data_quality`): missing-odds rate, void/postponed flags,
      dedupe, promoted/relegated team continuity.
- [ ] football-data.org fetcher (optional, key-gated): CL/WM fixtures/results → canonical `matches`
      (no odds). Degrades gracefully to "no key → skip" without failing the pipeline.
- [ ] Tests: column-mapping on a recorded CSV fixture, cache read-through, closing-vs-pre-match
      labeling, no-live-network guarantee.
Acceptance: `scripts/ingest.py` builds canonical Parquet for the Top-5 from cached fixtures; gate green.

## Phase 2 — Goal model (Dixon-Coles + Elo)

Goal: pre-match probabilities for 1X2 + O/U2.5 from a fitted goal model, honestly validated.
Add `scipy` (MLE) with justification.

- [ ] Elo/attack-defence baseline ratings (simplest reference).
- [ ] Dixon-Coles: bivariate Poisson + low-score correction + exponential time-decay; MLE fit on
      matches strictly BEFORE the prediction matchday.
- [ ] Derive full scoreline distribution → 1X2 probs + P(Over/Under 2.5).
- [ ] Calibration report: reliability curve + Brier + log-loss vs. the closing-line-implied probs.
- [ ] Tests: leakage guard (fit window excludes target matchday), deterministic seed, probability
      sums, known-fixture sanity.
Acceptance: `reports/model_eval.json` + markdown; if Dixon-Coles is not better-calibrated than the
closing line (it usually is not), that is the reported finding.

## Phase 3 — Value & selection

Goal: turn model probs + market odds into value bets, vig-honest.

- [ ] Implied-prob-from-odds with **overround removal** (proportional + a note on why it matters).
- [ ] Edge = `p_model * odds - 1`; value-bet selection above a threshold; markets 1X2 + O/U2.5.
- [ ] Wettschein/accumulator builder: assemble a slip from a day's picks, tracked as a SEPARATE
      track with an explicit note that accumulators compound the margin and are −EV.
- [ ] Tests: overround removal math, edge sign, void handling, accumulator odds product.
Acceptance: given predictions + odds, emits a ranked value-bet list per matchday; gate green.

## Phase 4 — Backtest engine (first real run — the core deliverable)

Goal: walk-forward bankroll simulation over the Top-5, honest metrics, baselines.

- [ ] Walk-forward loop: per matchday fit model on past only → value bets → settle at real odds
      (place at pre-match, measure CLV vs. closing).
- [ ] Bankroll accounting + staking: flat 1u AND 0.25-Kelly as two paper accounts (per-bet cap).
- [ ] Metrics: ROI, yield (profit/turnover), max drawdown, calibration, CLV; rule-generated verdict.
- [ ] Baselines: always-home, always-favorite, always-over-2.5, closing-line-implied.
- [ ] Shift-test (lag inputs one matchday) as a leakage check.
- [ ] Tests: known-outcome settle math, staking math, deterministic run, baseline correctness.
- [ ] **Run `betting-methodology-reviewer`** on `value/` + `backtest/` before claiming any result.
Acceptance: `scripts/run_backtest.py` produces the bankroll curve + metrics JSON for 2019/20+;
honest finding reported (likely: does not beat the closing line).

## Phase 5 — ML challenger (walled off)

Goal: LightGBM that must beat Dixon-Coles AND the closing line to count. Add `lightgbm`.

- [ ] Feature dataset (pre-match only: ratings, form, rest days, home/away, market-implied prob).
- [ ] Purged + embargoed walk-forward validation.
- [ ] Honest scorecard: Brier, log-loss, ROI vs. Dixon-Coles + closing line, shift-test, trial log
      with a rising significance hurdle (DSR/PBO analog).
Acceptance: `reports/ml_eval.json`; the negative result (if the GBDT does not robustly beat both)
is reported, not hidden.

## Phase 6 — Forward paper loop

Goal: stateful, idempotent loop that accumulates real-time P&L.

- [ ] Verify: does the current-season football-data.co.uk CSV include unplayed fixtures with
      pre-match odds? If yes → bet Top-5 with no key. If no → fixtures via football-data.org
      (shadow-mode for those).
- [ ] Forward loop: pull upcoming fixtures + pre-match odds → log bets at `timestamp_known` → settle
      after results → snapshot bankroll. Idempotent (re-run on same date = no-op).
- [ ] Persistent bet ledger + `bankroll_snapshots` as committable derived artifacts under `data/`.
- [ ] CL/WM shadow-mode: log model probabilities, no stake.
- [ ] Tests: idempotency, settle-on-result, dedupe by `bet_id`.
Acceptance: `scripts/run_forward.py` advances one matchday, is safe to re-run, writes the ledger.

## Phase 7 — GitHub Actions pipeline (Needs Nico: remote + key)

- [ ] `ci.yml`: uv sync + ruff + pytest on push/PR.
- [ ] `pipeline.yml`: cron ingest + forward-settle + publish; weekly full re-eval; git-scraping
      derived artifacts back (raw CSVs stay out); Issues-on-failure (create `pipeline` label once).
- [ ] `.env.example` + secret wiring for `X-Auth-Token` (optional CL/WM).
Acceptance: workflows valid; documented; first scheduled run is a Needs-Nico gate (remote + key).

## Phase 8 — Dashboard

- [ ] FastAPI read API over the ledger + reports.
- [ ] React 19 + Vite + hand-rolled SVG charts: bankroll curve, calibration, per-market/per-league
      ROI, CLV distribution, upcoming picks (with shadow-mode label for CL/WM).
- [ ] Disclaimer banner on every view.
Acceptance: `npm run build` passes; dashboard renders from committed derived artifacts.

## Phase 9 — Publish

- [ ] README polish (blockquote disclaimer, honest-harness table, badges, screenshots, reproduction).
- [ ] Secret scan over history; credit football-data.co.uk; confirm no raw CSVs committed.
- [ ] Portfolio entry (add to `~/private/portfolio`).
Acceptance: publish checklist (see `~/.claude/CLAUDE.md`) satisfied; Needs-Nico for the public flip.

## Standing mandate (per AUTOPILOT, once per phase — not per iteration)

- [ ] Research current best practice (recent football-modeling papers, strong public repos, closing-
      line-value literature) and challenge this plan. If materially better, write an ADR
      (`docs/adr/`) and adjust. Default to shipping; reopen a decision only with a sourced reason.

## Needs Nico (loop cannot do these itself)

- Git remote / public-visibility decision before any first push.
- football-data.org free API key (`X-Auth-Token`) as a repo secret (optional; core needs no key).
  Do NOT sign up for anything paid.
- The Odds API key (optional, later) for real forward CL/WM P&L.
- Merges to `main`.
