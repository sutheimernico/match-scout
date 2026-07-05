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
- [x] football-data.org fetcher (key-gated): CL/WC/EC fixtures/results → canonical `matches`
      (no odds → shadow-mode). Degrades to "no key → clear error, skip". DONE 2026-07-05
      (`data/football_data_org.py`, `config.py` .env loader; key in `.env`, gitignored). KEY PROVIDED
      + LIVE-VERIFIED: WC 2026 (104 matches, tournament in progress) + CL 2024/25 (189) fetched clean.
- [x] Tests: column-mapping on synthetic both-era frames (D8), cache read-through, closing-vs-
      pre-match labeling, `book` separation, retry, no-live-network guarantee. DONE 2026-07-05.
Acceptance: `scripts/ingest.py` builds canonical Parquet for the Top-5 (1X2 from 2013/14+, O/U2.5
from 2019/20+) from cached fixtures; gate green. — MET (live-verified 2026-07-05).

## Phase 2 — Goal model (Dixon-Coles + Elo)

Goal: pre-match probabilities for 1X2 + O/U2.5 from a fitted goal model, honestly validated.
Add `scipy` (MLE) with justification.

- [x] ρ=0/no-decay Poisson ablation (D9). DONE 2026-07-05: `model/poisson.py` (scoreline→markets)
      + `model/goal_model.py` (MLE fit of attack/defence + home_adv, ridge shrinkage). VERIFIED on
      real E0 2023/24: top attack Man City/Arsenal/Newcastle, best defence Arsenal, home_adv +0.20 —
      recovers reality. Elo-proper rating baseline optional/deferred (the Poisson ablation covers it).
- [x] Dixon-Coles: **τ low-score correction** (4-cell, fitted ρ bounded to keep τ>0) +
      exponential **time-decay** (half-life, as-of) on the base fit; single global home-advantage.
      DONE 2026-07-05 (`fit_dixon_coles`, `_apply_tau`, 3 tests). **ξ still to be tuned via held-out
      log-lik/Brix in the calibration/walk-forward step (not hardcoded)** — next bullet.
- [ ] Promoted-team cold-start: shrink new-team attack/defence toward the league mean, regularization
      weight decaying with match count (D9).
- [x] Derive full scoreline distribution → 1X2 probs + P(Over/Under 2.5). DONE 2026-07-05
      (`model/poisson.py`). τ-renormalization for Dixon-Coles handled in the DC bullet above.
- [x] Calibration report: Brier + log-loss vs. the closing-line-implied probs (Shin-de-vigged
      Pinnacle closing). DONE 2026-07-05 (`evaluation/metrics.py`, `evaluation/walk_forward.py`,
      `evaluation/calibration.py`, `scripts/eval_model.py`). MEASURED on E0 2022/23–2023/24 (675
      matches, walk-forward, min_train 80, half-life 180d): model Brier 0.570 / log-loss 0.965 vs.
      market Brier 0.547 / log-loss 0.930 → **model does NOT beat the closing line** (the honest,
      expected finding). Reliability curve helper available; not yet plotted (dashboard, Phase 8).
- [ ] Tests: leakage guard (fit window excludes target matchday, hard error), fitted ρ sign +
      reasonableness bound, renormalization tolerance, deterministic seed, **numeric cross-check vs.
      penaltyblog** (offline; adopting it as a dependency → Needs Nico).
Acceptance: `reports/model_eval.json` + markdown; if Dixon-Coles is not better-calibrated than the
closing line (it usually is not), that is the reported finding.

## Phase 3 — Value & selection

Goal: turn model probs + market odds into value bets, vig-honest.

- [x] De-vig for the benchmark via **Shin's method** (default) + proportional as a sensitivity
      check (proportional has a favourite-longshot bias, D6). De-vig builds the benchmark/calibration
      probability only — NOT a selection input. DONE 2026-07-05 (`value/devig.py`, Shin via brentq,
      favourite-longshot correction verified, 7 tests).
- [x] Edge = `p_model * odds - 1` on the **Bet365 pre-match** price (D5) — the SOLE selection path
      (D6); value-bet selection above a threshold; markets 1X2 + O/U2.5. Never price at `Max`/`Avg`.
      DONE 2026-07-05 (`value/edge.py`: `edge`, `select_value_bets`; ignores closing/other books,
      sorted by edge; 6 tests).
- [ ] Wettschein/accumulator builder (SECONDARY track, D10): assemble a slip from a day's picks,
      explicitly framed + reported as the honest demonstration that accumulators compound the margin
      and are −EV. Not a headline result.
- [ ] Tests: Shin/proportional de-vig math, edge sign, single-book pricing, void handling,
      accumulator odds product.
Acceptance: given predictions + odds, emits a ranked value-bet list per matchday; gate green.

## Phase 4 — Backtest engine (first real run — the core deliverable)

Goal: walk-forward bankroll simulation over the Top-5, honest metrics, baselines.

- [x] Walk-forward loop → value bets → **settle at the taken Bet365 pre-match price** (D4); Pinnacle
      closing feeds ONLY CLV. DONE 2026-07-05 (`backtest/engine.py`).
- [x] Bankroll + staking: **flat = headline**; 0.25-Kelly SECONDARY (edge-shrink hook, per-bet cap
      ≤5%, D10). DONE 2026-07-05 (`backtest/staking.py`).
- [ ] Trial log + whole-harness anti-overfit (D1): log EVERY config tried, counting subgroup slices
      as trials; rising significance hurdle (DSR/PBO analog) on the Dixon-Coles path; pre-register /
      design-vs-holdout split. STILL OPEN — threshold/min_train/half-life knobs not yet trial-logged.
- [x] Metrics + verdict (D2): yield-with-bootstrap-CI, drawdown, CLV + CLV beat-rate, min-bet-count
      CI-vs-0 verdict. DONE 2026-07-05 (`backtest/metrics.py`).
- [x] Leak guards (D3): hard fit-window (walk-forward no-lookahead PROVEN by test) + odds-provenance
      (selection ignores `is_closing` rows, tested) + **label-permutation/placebo test**
      (`backtest/placebo.py`, detects a guaranteed-win leak, 2 tests). DONE 2026-07-05.
- [x] Baselines: always-home, always-favorite, always-over-2.5. DONE 2026-07-05
      (`backtest/baselines.py`).
- [x] Tests: settle math, staking math, deterministic run, baseline correctness, CLV present/absent.
      DONE (placebo test pending with the D3 item).
- [x] **Ran `betting-methodology-reviewer`** (D-requirement). Verdict: headline "no edge/negative
      CLV" credible (walk-forward/vig/settlement/CLV verified clean); found 🔴 broken placebo null +
      🟡 stake-invariant Kelly CI — BOTH FIXED (ADR 0002). Corrected market-null centers at CLV
      (−5.45% ≈ −5.36%), real −4.7% sits inside → no edge, no leak confirmed. D1 (trial log/ξ-tune)
      still open; report as "no edge under this untuned config".
Acceptance: `scripts/run_backtest.py` produces yield-CI/CLV/drawdown + baselines + verdict. MET
2026-07-05 (E0 2022/23–2023/24): 971 value bets, flat yield −4.7% (CI [−13.0%, +4.1%] straddles 0),
CLV mean −5.4%, CLV beat-rate 20.4% → **no evidence of an edge; value bets have negative CLV** — the
expected honest finding. Baselines (flat yield): home +1.0%, favorite +0.9%, over −0.7%.

## Phase 5 — ML challenger (walled off)

Goal: LightGBM that must beat Dixon-Coles AND the closing line to count. Add `lightgbm`.

- [x] Feature dataset (pre-match, leak-free): Dixon-Coles walk-forward probs + Shin-de-vigged market
      probs. DONE 2026-07-05 (`ml/dataset.py`, 4 tests). Raw form/rest-days deferred (base features
      already suffice — the GBDT underperforms them, see finding).
- [x] Purged + embargoed walk-forward validation. DONE 2026-07-05 (`ml/validation.py`:
      `purged_walk_forward_splits`, expanding-window + embargo gap, 7 tests).
- [x] Honest scorecard: OOS Brier + log-loss vs. Dixon-Coles + closing line over purged/embargoed
      folds, rule-generated verdict (D11 note baked in). DONE 2026-07-05 (`ml/evaluate.py`,
      `scripts/run_ml.py`, native LightGBM Booster API — no scikit-learn dep; 3 tests). The DSR/PBO
      trial hurdle is the shared D1 item (Phase 4), still open.
Acceptance: MET 2026-07-05 (E0 2022/23–2023/24, 563 OOS): ML Brier 0.774 / log-loss 1.674 vs. DC
0.563 / 0.952 vs. market 0.539 / 0.917 → **ML beats NEITHER; the naive GBDT overfits the small
sample (log-loss worse than uniform) and is beaten by the statistical baseline** — the honest
negative result, reported not hidden.

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
- ~~football-data.org free API key~~ — PROVIDED 2026-07-05 (in `.env`, gitignored, live-verified).
  For GitHub Actions it must also be added as a repo secret `FOOTBALL_DATA_API_KEY`.
- The Odds API key (optional, later) for real forward CL/WM P&L.
- Merges to `main`.
