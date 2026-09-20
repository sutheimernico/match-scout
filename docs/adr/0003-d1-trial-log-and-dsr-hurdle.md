# ADR 0003 — D1 closed: append-only trial log + trials-adjusted DSR hurdle

**Status:** Accepted (2026-09-20) · **Closes:** ADR 0001 D1 (open since 2026-07-05, restated as
open in ADR 0002)

## Context

D1 was the project's own biggest honesty item: the Dixon-Coles path has free knobs (edge
threshold, burn-in `min_train`, time-decay half-life ξ, staking, league/market scope) and nothing
recorded how many of them had been tried. Both prior ADRs could only *assert* "only one config was
ever run"; nothing made that checkable, and nothing would have stopped a future session from
quietly searching until something looked profitable. Until D1 closed, every finding had to be
labelled "no edge under this untuned config".

A bootstrap CI answers "could this one result be luck?". It does not answer "could the best of N
tried results be luck?" — that is what a multiple-trials correction is for.

## Decision

- **Every run is a trial, forever.** `src/matchscout/evaluation/trial_log.py` appends one JSONL
  entry per `scripts/run_backtest.py` invocation to `data/trial_log.jsonl` — unconditionally, with
  no flag to skip it. The entry carries the config (hashed to a stable `trial_id`), the headline
  metrics including the per-bet Sharpe, the git commit, and a timestamp. The log is a committed
  derived artifact, so the search history travels with the repo.
- **Subgroup slices count as trials** (the D1 requirement). Per-league / per-market cuts are logged
  with `kind: "slice"`. Five ways to look at one result are five chances to find a flattering one.
- **History backfilled, and labelled as such.** `scripts/backfill_trial_log.py` reconstructs the
  2026-07-05 runs from the written record (PLAN.md Phase 4 acceptance + the committed
  `site/public/data/backtest.json`): the E0 run, the Top-5 run, and the five per-league slices —
  seven entries, all `backfilled: true`. Their per-bet return series was never retained, so their
  `sharpe` is `null` rather than invented. ADR 0002's "only one config ever ran" is now visible as
  what it was: one *headline* config, plus five slices of a second one.
- **The hurdle rises with the search.** `src/matchscout/evaluation/dsr.py` implements the Deflated
  Sharpe Ratio (Bailey & López de Prado 2014) over the per-bet return series: the bar is the
  expected maximum Sharpe that N independent zero-edge trials would produce anyway, and an edge
  claim needs DSR > 0.95 (adjusted p < 0.05). `V[SR]` is measured across the logged trials when two
  or more carry a Sharpe, otherwise it falls back to the null sampling deviation `1/sqrt(T-1)`.
  Every backtest summary now ends with a rule-generated line naming the trial count.
- **Pre-registration rule for future config changes (design vs. holdout).** Seasons 2022/23–2023/24
  are hereby the **design fold** — every config tried so far has seen them, so no result on them can
  ever be a clean out-of-sample claim. Any later season (2024/25 onwards) is the **holdout fold**
  and is spent once: a config is frozen and logged *before* it touches holdout data, and the holdout
  result is reported whatever it says. The forward paper loop (Phase 6) is the strongest form of
  this — it cannot see its data before deciding, by construction.

## Rejected / deferred

- **PBO (probability of backtest overfitting).** It needs combinatorially split backtest paths,
  which this harness does not produce, and faking the splits would be worse than not having the
  statistic. The trial count is the honest thing available and it grows by itself.
- **Deduplicating repeated identical configs in the log.** Re-running a config is a real event and
  stays on the record; the DSR is deflated by the number of *distinct* configs, so a re-run does not
  inflate the bar.
- **Counting the Premier-League slice and the E0-only run as one trial.** They are numerically the
  same computation, but they are logged as two entries. That over-counts the search by one, which
  raises the bar — the conservative direction.

## Consequences

- The standing caveat "no edge under this untuned config" is replaced by a measured statement. On
  the E0 2022/23–2023/24 configuration (971 bets, flat): per-bet Sharpe −0.0347 against a +0.0445
  bar from 7 logged trials → **DSR 0.008, hurdle not met**. The result was negative before the
  correction and is more clearly negative after it.
- Tuning ξ (the D9 open item) is no longer free: each attempt is a logged trial that raises the bar
  for every later claim. That is the intended cost.
- `data/` now exists as the committed derived-artifact directory (trial log; the forward ledger and
  bankroll snapshots join it in Phase 6). Raw source CSVs remain excluded.
