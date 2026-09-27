# Plan: Forward Proof + Rigor — match-scout

**Date:** 2026-07-21 · **Status:** awaiting go · **Executor:** any capable agent (self-contained — no session context required)
**Hard boundary, restated first:** paper-only. Nothing in this plan may move toward real betting — no bookmaker accounts, no stake execution, no "how to bet" framing. The project is an honest measurement harness whose headline finding is *negative* (the market wins), and that stays its identity.

## Context (verified 2026-07-21 by code review)

match-scout: honest football prediction + betting-slip **simulation** (Top-5 leagues, Dixon-Coles MLE + walled-off LightGBM challenger, Shin de-vig for benchmarks, EV on real with-vig prices, CLV vs. Pinnacle closing, stake-weighted bootstrap CIs, placebo/market-null test). 139 tests green (~31s), ruff clean. Phases 0–5 + 8 (dashboard) done with **documented negative results**: DC does not beat the closing line (Brier 0.570 vs. 0.547); 4,540 bets across Top-5 yield −8.78% with CI excluding 0; the ML challenger beats nothing. ADR 0002 documents a real self-found placebo-null bug and its fix. Methodology is double-guarded (schema-level `timestamp_known <= timestamp_event` + behavioral no-lookahead test).

What's missing, per both reviews and the project's own docs:
- **Phase 6 (forward paper loop) — the core gap.** Everything is historical backtest; there is no live, growing paper track record. `data/` (ledger/bankroll artifacts) doesn't even exist yet. Only the CL/WM shadow *tips* display exists.
- **Phase 7 (CI) — at zero.** No workflow file anywhere in the repo; "self-operating pipeline" (README line 3) is currently aspiration.
- **D1 (trial log + DSR hurdle) — the project's self-declared biggest honesty item.** Per ADR 0001/0002: every tried configuration (edge threshold, market, league, ξ, staking, min-odds — and every subgroup slice) counts as a trial; a rising significance hurdle (Deflated Sharpe Ratio / PBO analog) must apply to the whole DC path. Today only one config was ever run (so no cherry-picking *yet*), but nothing enforces that going forward; no trial-log/DSR code exists. Until closed, findings must read "no edge under this untuned config".
- **D7 (odds-timestamp data quality) never measured**: the pre-`C` vs. `C` odds-gap analysis that empirically grounds whether "edge vs. closing" measures signal at all.
- **README is stale and wrong in places**: shows Phases 1–8 unchecked ("Early build") though 1–5+8 are done; still cites the removed "shift-test" as an active guard (replaced by `market_null_test`).
- Model-level lookahead trust: `fit_dixon_coles` (`src/matchscout/model/goal_model.py`) relies entirely on caller discipline (`walk_forward.py`'s `< day` filter) — Phase 2's own open item.
- Small: `ml/dataset.py` docstring claims "point-in-time by construction" for a closing-odds feature (closing prices only exist at kickoff — imprecise wording; harmless since `ml/` is walled off from selection).
- Calibration reliability plots: helper exists (`evaluation/calibration.py`) but "not yet plotted".

Principles (keep): raw CSVs never committed; provider seams + fakes (no network in tests); negative results reported plainly; benchmark-first (CLV over ROI); no remote exists — never push (remote creation is Needs Nico).

## Goal

Turn the finished backtest into a living, self-proving paper system (forward ledger + CI-ready automation), close the two self-declared rigor debts (D1, D7), and surface the story that makes this a standout "honest quant methodology" piece — calibration visuals, CLV deep-dive, and a README that finally matches reality.

## Execution rules

- Branch `feat/forward-and-rigor` off the current branch. Conventional Commits, English. Gates after every task: `uv run pytest -q && uv run ruff check .`; dashboard tasks additionally build the site (`npm --prefix site run build` or the repo's documented equivalent).
- Data discipline: derived artifacts only under `data/` (ledger, snapshots — JSON/parquet, schema-documented); raw football-data CSVs stay out of git (existing `.gitignore` discipline).
- Every number shown in dashboard/README must trace to a committed derived artifact or a test-pinned computation.

---

## Phase A — Truth & guards (cheap, do first)

### Task 1: README reality-sync
**Files:** `README.md`.
Phase checkboxes match PLAN.md (1–5+8 done, with the honest one-line result each — including the negative ones); replace the stale "shift-test" bullet with the actual guard set (schema validator, behavioral no-lookahead test, market-null/placebo per ADR 0002); pipeline claims labeled "planned (Phase 6/7)" until true.
**Accept:** no claim in README contradicts PLAN.md/ADRs; negative headline results visible, not buried.

### Task 2: Hard lookahead guard in the model layer
**Files:** `src/matchscout/model/goal_model.py`, callers, tests.
`fit_dixon_coles` gains a required `as_of` parameter and raises on any training row with `date >= as_of` (hard error, closing Phase 2's open item). `walk_forward.py` passes its day; the future forward loop inherits the protection by construction.
**Accept:** test proves the guard trips on a poisoned frame; all existing tests green.

### Task 3: Trial log — every run is a trial, forever
**Files:** new `src/matchscout/evaluation/trial_log.py`, wiring into `scripts/run_backtest.py`, tests.
Append-only JSONL (`data/trial_log.jsonl`, committed): full config hash + parameters (threshold, ξ/half-life, staking, min_train, league/market scope, code version), headline metrics, timestamp. Every `run_backtest.py` invocation logs unconditionally — no flag to skip. Backfill one entry for the historical single config (from PLAN.md's recorded results, marked `backfilled: true`).
**Accept:** running the backtest twice yields two entries; log schema documented in the file header; ADR 0002's "only one config ever ran" becomes verifiable instead of asserted.

### Task 4: ML docstring precision
**Files:** `src/matchscout/ml/dataset.py`.
Reword: the closing-probability feature is available only at kickoff; the challenger is therefore a *market-relative diagnostic*, not a deployable pre-match model — which is exactly its D11 purpose. Two sentences, no code change.
**Accept:** no "point-in-time by construction" claim on a closing-price feature remains.

---

## Phase B — D7: measure the premise

### Task 5: Odds-timestamp gap analysis
**Files:** new `scripts/analyze_odds_gap.py`, report artifact `data/odds_gap_report.json`, short section in README/dashboard, tests on the computation.
With the already-cached Top-5 data: quantify the pre-match (Bet365) vs. closing (Pinnacle) price gap distribution per league/market — the line movement that CLV measurement presupposes. Honest conclusion either way: if movement is substantial, CLV is meaningful signal; if negligible in some segment, say the CLV benchmark is weak there.
**Accept:** report artifact committed + pinned by test on a fixture; one paragraph of findings with the same hedged tone as the rest of the project.

---

## Phase C — Phase 6: the forward paper loop (the core)

### Task 6: Ledger schema + persistence first
**Files:** new `data/` layout (`bets.jsonl` ledger, `bankroll_snapshots.jsonl`), `src/matchscout/forward/ledger.py`, schema doc, tests.
Canonical tables per PROJECT.md §4: bets keyed by deterministic `bet_id` (fixture + market + selection + timestamp_known), status `pending → settled/void`; snapshots append-only. Idempotency at the storage layer: re-inserting an existing `bet_id` is a no-op.
**Accept:** round-trip + idempotency + dedupe tests; schema documented before the loop exists (format decided deliberately, not ad hoc).

### Task 7: The loop itself
**Files:** new `src/matchscout/forward/loop.py`, `scripts/run_forward.py`, tests with fake providers.
Steps per run: (1) fetch current-season fixtures + pre-match odds — **decision tree** per PLAN.md: if the current football-data.co.uk season CSV carries unplayed fixtures with odds, use it; else fixtures via football-data.org (API key, Needs Nico) in shadow mode with odds "unavailable" honestly recorded; (2) select bets with the frozen config (the Task-3-logged one — changing it = new trial entry, automatically); (3) log at `timestamp_known`; (4) settle played fixtures; (5) append bankroll snapshot. Fully idempotent — safe to re-run any number of times per day (Task 6 guarantees it).
**Accept:** fake-provider end-to-end test: two runs same day → identical ledger; fixture plays → settled exactly once; missing odds → honest shadow entry, never invented prices.

### Task 8: Forward track record on the dashboard
**Files:** `site/` (new panel), export step, tests where the repo's site testing allows.
"Paper-Forward seit <Datum>": growing bankroll curve, bet count, running yield + CI, CLV-beat-rate — plus the immovable disclaimer ("Simulation. Erwartung laut Backtest: Verlust gegen den Markt."). Honest empty state before data matures.
**Accept:** renders from committed artifacts in all three states (empty/pending/settled); disclaimer not dismissible.

---

## Phase D — Phase 7: CI (authored now, activated on Nico's remote)

### Task 9: Workflows
**Files:** `.github/workflows/ci.yml` (uv sync + ruff + pytest on push/PR), `.github/workflows/pipeline.yml` (cron: forward loop → settle → export → commit-back `[skip ci]` → Issue on failure — grid-scout's proven pattern), `.env.example`.
Keep all logic in the tested Python CLIs; workflow bash stays one-liners. Secrets referenced (`FOOTBALL_DATA_API_KEY`), never present.
**Accept:** `actionlint` (if available) clean; workflows are inert until a remote exists — documented plainly in README.

---

## Phase E — The story layer (cheap, high-visibility)

### Task 10: Calibration reliability plots
**Files:** dashboard panel + export using the existing `evaluation/calibration.py` helper.
DC vs. market reliability curves (the classic honest-quant visual — the math already exists, it was just never plotted). Shadow-mode overconfidence (Brazil 98%) shown as the cautionary example it is.
**Accept:** curves render from committed eval artifacts; axes/binning pinned by test.

### Task 11: CLV deep-dive page
**Files:** dashboard panel + export, tests on the aggregations.
CLV distribution per bet, CLV by odds band, beat-rate over time, and a plain-language explainer why CLV beats ROI as a truth signal — grounded in the Task-5 gap analysis.
**Accept:** every figure from committed artifacts; explainer references the measured gap, not folklore.

### Task 12: Subgroup explorer with built-in multiple-comparisons honesty
**Files:** dashboard panel, tests.
Slice yield/CLV by league/market/odds band — every slice view displays "Achtung: Subgruppen-Slices sind Trials (siehe D1)" and the number of implied comparisons. Slicing must not silently become cherry-picking; the UI itself teaches why.
**Accept:** warning is structural (rendered with every slice), not a footnote.

### Task 13: D1 closure — the DSR hurdle
**Files:** new `src/matchscout/evaluation/dsr.py`, integration into `run_backtest.py` summary + dashboard, ADR addendum, tests against hand-computed references.
Deflated-Sharpe-Ratio-analog hurdle over the trial log: given N logged trials, the significance bar for "edge" rises accordingly; the verdict line in every backtest summary becomes "edge claim requires DSR-adjusted p < 0.05 across N trials — current: …". Design-fold vs. holdout-fold split documented in the ADR addendum (pre-registration style for future config changes).
**Accept:** hand-computed reference test; with today's trial count the verdict correctly reads "no edge under untuned config, hurdle not met"; ADR 0001's D1 marked closed with a dated addendum.

---

## Verification before completion
1. `uv run pytest -q` (139 + new) and `uv run ruff check .` green; site builds; forward-loop end-to-end fake run green.
2. Consistency sweep: README ↔ PLAN.md ↔ ADRs (no stale shift-test/phase claims); every dashboard number traces to an artifact; paper-only disclaimer present on every new surface.
3. Two consecutive `run_forward.py` runs on fixtures → provably idempotent ledger.
4. Append an **Outcome** section here: built/deviations, D7 findings summary, trial-log state, open items.

## Needs Nico (not agent-executable)
- Go for this plan. **Also: veto option** — this project was flagged as borderline in the review operation (betting simulation); if he'd rather freeze it, Phase A alone (truth & guards) is a worthwhile minimal go.
- Remote + repo secret (`FOOTBALL_DATA_API_KEY`, free tier) to activate Phase 6/7 in CI; until then the forward loop runs locally/manually.
- Publish decision later (separate publish-checklist run); the "honest quant methodology" README framing from Task 1 doubles as the portfolio text when that day comes.

---

## Outcome (2026-09-27)

Executed on branch `feat/forward-proof` (not `feat/forward-and-rigor` as written above). Gate
186 → 205 tests green, ruff clean, site builds. No remote, nothing pushed.

| Task | State | Evidence |
| --- | --- | --- |
| 1 README reality-sync | done | README rewritten: phases with honest one-liners, real guard set (no shift-test), matchday how-to |
| 2 Hard lookahead guard | done | `7ba2f7f` — `fit_dixon_coles(as_of=…)` raises on rows ≥ as_of |
| 3 Trial log | done | `78ea05d` — `data/trial_log.jsonl`, 8 entries incl. backfill + forward config |
| 4 ML docstring | done | `065c37c` |
| 5 D7 odds gap | done | `afe8bd2` — `data/odds_gap_report.json` |
| 6 Ledger | done | `4c99d4b` |
| 7 Forward loop | done | `e3eacf0`, fixed in `be7d1bd` (see deviations), predictions log `91ca1f4` |
| 8 Forward on dashboard | done | `0d30040` panel + `3b9313e` German Spieltag page |
| 9 Workflows | done, inert | `1537ce3` — no actionlint on this machine; YAML parse-checked only |
| 10 Calibration plots | **open** | not started |
| 11 CLV deep-dive | **open** | not started |
| 12 Subgroup explorer | **open** | not started |
| 13 DSR hurdle | done | `90e8aa7` — ADR 0003; hurdle not met across 8 trials |

**D7 findings.** Over 5,580 Top-5 matches (2022/23–2026/27) the Shin de-vigged gap between the
Bet365 pre-match price and the close has a median of 1.2–1.3 pp (1X2) and 1.8–2.1 pp (O/U 2.5)
against every reference close (Bet365, Pinnacle, market average); 57–74 % of prices move ≥ 1 pp.
No segment is weak — CLV is a meaningful yardstick wherever the harness bets. Pinnacle disappears
from the source mid-2025/26, so the forward loop measures CLV against the market-average close and
records that per bet.

**Forward state.** Run 2026-09-20 placed 12 paper bets; run 2026-09-27 settled them: 1 won,
−105 units on 120 staked (yield −87.5 %, CI [−100 %, −62 %]), CLV beat 0/12 vs. the
market-average close. n = 12 — no verdict, and the page says so. 2026-09-27 is inside an
international break: the feed has no Top-5 fixtures; the next Top-5 matchday is 9–10 Oct 2026
(football-data.org schedule), which the local cron will pick up once the prices are published.

**Deviations.**
- *Stale season cache (bug found by the first live run).* `FootballDataCoUk` never refreshed the
  running season, so the loop would have trained on an old table and never settled. Fixed:
  `live_seasons` refetch once per run; fixtures feed cached per run hour (an evening run must see
  the afternoon's prices).
- *Prediction log added* (`data/predictions.jsonl`): the plan only logged bets. Every priced
  fixture is now recorded with the de-vigged market view, so calibration can be measured on the
  unselected sample. First priced sighting wins.
- *Local cron instead of CI* (08:47/17:47, `scripts/run_matchday.sh`, flock, never commits),
  because the CI schedule is inert without a remote. Undo: `crontab -l | grep -v 'match-scout' |
  crontab -`; pre-change backup in `logs/crontab.backup-2026-09-27`.
- *Dashboard panel in English, Spieltag page in German:* the dashboard is the English portfolio
  surface; the Spieltag page is Nico's own matchday view.
- *Tasks 10–12 left open:* work stopped when the auto-mode permission classifier began denying
  further reads in the session (it flagged the crontab entry as unauthorized persistence).

**Open items.** Tasks 10–12; Pages deploy + weekly re-eval in `pipeline.yml`; `timestamp_known`
imputation for the backtest (D7 remainder); decide cron vs. CI once a remote exists.
