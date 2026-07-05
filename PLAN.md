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

- [x] Provider seam: `MatchProvider` + `OddsProvider` Protocols (`@runtime_checkable`); canonical
      `matches`/`odds` schema (enums + `validate_*` enforcing the no-lookahead + odds invariants);
      `FakeProvider` backing network-free tests. DONE 2026-07-05: 13 tests, gate green.
- [x] football-data.co.uk fetcher + per-era column mapping (D8). DONE 2026-07-05: `parse()` (both
      eras, B365/PS/PSC/Avg extraction), `fetch_raw` (httpx, injectable client, retry/backoff),
      `FootballDataCoUk` provider, read-through `.cache/` cache, `scripts/ingest.py` CLI. VERIFIED
      LIVE: ingested Top-5 × {2324 flat, 1718 Bb} = 3578 matches / 78,023 odds rows, schema-valid,
      0 lookahead violations, Pinnacle-closing present in both eras. 11 tests.
- [ ] Read-through cache freshness (extends the above): skip complete past seasons, refresh current
      season vs. injected run-date. Basic exists-or-fetch + `refresh` flag done; season-freshness
      logic deferred to the forward loop (Phase 6).
- [ ] Odds-timestamp data-quality check (D7): measure pre-`C` vs `C` odds gap/variance; confirm
      pre-match columns precede kickoff; document `timestamp_known` imputation (kickoff − N h).
- [ ] Canonical `data_quality` report (schema + validators DONE in iter 1): missing-odds rate,
      void/postponed flags, dedupe, promoted/relegated team continuity.
- [ ] football-data.org fetcher (optional, key-gated): CL/WM fixtures/results → canonical `matches`
      (no odds). Degrades gracefully to "no key → skip" without failing the pipeline.
- [x] Tests: column-mapping on synthetic both-era frames (D8), cache read-through, closing-vs-
      pre-match labeling, `book` separation, retry, no-live-network guarantee. DONE 2026-07-05.
Acceptance: `scripts/ingest.py` builds canonical Parquet for the Top-5 (1X2 from 2013/14+, O/U2.5
from 2019/20+) from cached fixtures; gate green. — MET (live-verified 2026-07-05).

## Phase 2 — Goal model (Dixon-Coles + Elo)

Goal: pre-match probabilities for 1X2 + O/U2.5 from a fitted goal model, honestly validated.
Add `scipy` (MLE) with justification.

- [ ] Elo/attack-defence baseline ratings + a ρ=0/no-decay Poisson ablation (D9).
- [ ] Dixon-Coles: **independent Poisson + τ low-score correction** (4-cell) + exponential
      time-decay; MLE (scipy) fit on matches strictly BEFORE the prediction matchday. Single global
      home-advantage constant. **ξ tuned via held-out log-lik/Brier (walk-forward), not hardcoded.**
- [ ] Promoted-team cold-start: shrink new-team attack/defence toward the league mean, regularization
      weight decaying with match count (D9).
- [ ] Derive full scoreline distribution → 1X2 probs + P(Over/Under 2.5); renormalize after τ.
- [ ] Calibration report: reliability curve + Brier + log-loss vs. the closing-line-implied probs.
- [ ] Tests: leakage guard (fit window excludes target matchday, hard error), fitted ρ sign +
      reasonableness bound, renormalization tolerance, deterministic seed, **numeric cross-check vs.
      penaltyblog** (offline; adopting it as a dependency → Needs Nico).
Acceptance: `reports/model_eval.json` + markdown; if Dixon-Coles is not better-calibrated than the
closing line (it usually is not), that is the reported finding.

## Phase 3 — Value & selection

Goal: turn model probs + market odds into value bets, vig-honest.

- [ ] De-vig for the benchmark via **Shin's method** (default) + proportional as a sensitivity
      check (proportional has a favourite-longshot bias, D6). De-vig builds the benchmark/calibration
      probability only — NOT a selection input.
- [ ] Edge = `p_model * odds - 1` on the **Bet365 pre-match** price (D5) — the SOLE selection path
      (D6); value-bet selection above a threshold; markets 1X2 + O/U2.5. Never price at `Max`/`Avg`.
- [ ] Wettschein/accumulator builder (SECONDARY track, D10): assemble a slip from a day's picks,
      explicitly framed + reported as the honest demonstration that accumulators compound the margin
      and are −EV. Not a headline result.
- [ ] Tests: Shin/proportional de-vig math, edge sign, single-book pricing, void handling,
      accumulator odds product.
Acceptance: given predictions + odds, emits a ranked value-bet list per matchday; gate green.

## Phase 4 — Backtest engine (first real run — the core deliverable)

Goal: walk-forward bankroll simulation over the Top-5, honest metrics, baselines.

- [ ] Walk-forward loop: per matchday fit model on past only → value bets → **settle strictly at the
      taken Bet365 pre-match price** (D4); Pinnacle closing feeds ONLY the CLV metric.
- [ ] Bankroll accounting + staking: **flat 1u = headline** (order-independent); 0.25-Kelly a
      SECONDARY track — edge shrunk toward the market before staking, joint Kelly for same-day bets,
      hard per-bet cap ≤5% bankroll (D10).
- [ ] Trial log + whole-harness anti-overfit (D1): log EVERY config tried, counting subgroup slices
      (per-league/market/selection) as trials; rising significance hurdle (DSR/PBO analog) on the
      Dixon-Coles path; config pre-registered (or design-fold vs holdout-fold split).
- [ ] Metrics + verdict (D2): ROI-with-CI, yield, max drawdown, calibration, CLV + **CLV beat-rate**
      (headline); **CI-vs-baseline** rule-generated verdict with a minimum bet count.
- [ ] Leak guards (D3): hard fit-window assertion; **odds-provenance assertion** (selection path
      cannot read `is_closing=true` rows); **label-permutation/placebo test** (shuffle outcomes →
      ROI ≈ −vig). Shift-test kept only as a weak sanity check.
- [ ] Baselines: always-home, always-favorite, always-over-2.5, ρ=0-Poisson ablation, closing-line-
      implied.
- [ ] Tests: settle-at-taken-price assertion, staking math, deterministic run, baseline correctness,
      placebo collapses to −vig, odds-provenance holds.
- [ ] **Run `betting-methodology-reviewer`** on `value/` + `backtest/` before claiming any result.
Acceptance: `scripts/run_backtest.py` produces the calibration/CLV verdict (primary) + bankroll curve
+ metrics JSON (1X2 from 2013/14+, O/U2.5 from 2019/20+); honest CI-vs-baseline finding reported
(likely: does not beat the closing line).

## Phase 5 — ML challenger (walled off)

Goal: LightGBM that must beat Dixon-Coles AND the closing line to count. Add `lightgbm`.

- [ ] Feature dataset (pre-match only: ratings, form, rest days, home/away, market-implied prob).
- [ ] Purged + embargoed walk-forward validation.
- [ ] Honest scorecard: Brier, log-loss, ROI vs. Dixon-Coles + closing line, placebo test, trial log
      with a rising significance hurdle (DSR/PBO analog). **Note (D11): "beats Dixon-Coles" is
      near-guaranteed once the market-implied-prob feature is included and is uninteresting; only
      "beats the closing line" is the real test — the writeup must say so.**
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

- [x] **Phase 0→1 self-challenge DONE 2026-07-05** — 3-model council (Opus/Sonnet/Sonnet) →
      `docs/adr/0001-council-methodology-hardening.md` (D1–D11 folded into spec + this plan).
- [ ] Phase 1→2 and later boundaries: re-run the self-challenge; write an ADR if it changes the plan.

## Needs Nico (loop cannot do these itself)

- Git remote / public-visibility decision before any first push.
- football-data.org free API key (`X-Auth-Token`) as a repo secret (optional; core needs no key).
  Do NOT sign up for anything paid.
- The Odds API key (optional, later) for real forward CL/WM P&L.
- Merges to `main`.
