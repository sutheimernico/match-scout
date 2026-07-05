# ADR 0002 — Market-implied placebo null + stake-weighted Kelly CI

**Status:** Accepted (2026-07-05)

## Context

The `betting-methodology-reviewer` reviewed the value + backtest surface after the first real
backtest (E0 2022/23–2023/24: 971 value bets, flat yield −4.7%, CLV beat-rate 20.4%). It confirmed
the "no edge, negative CLV" headline as credible (walk-forward leak-freedom, vig/selection
discipline, settlement-at-taken-price, and the CLV path all verified clean), but found two genuine
bugs.

## Decision

- **🔴 Placebo/leak-guard null.** The original `_shuffle_outcomes` permuted match outcomes globally,
  ignoring each match's market-implied difficulty. Because value bets skew to underdog/long-odds
  selections, borrowing the favourite-dominated population base rate inflated the null to +18.8%
  yield — it could have masked a leak up to ~+15–18%. **Replaced** with a market-truth Monte-Carlo
  null (`market_null_test`): each bet's outcome is drawn from the market's de-vigged Pinnacle-closing
  probability for that selection. Under this null, betting at the taken price yields ≈ the CLV, so
  the null centers at the (independently-correct) mean CLV. Verified: corrected null mean −5.45%
  ≈ CLV mean −5.36%; observed −4.7% sits inside it (`real_exceeds_null_95pct=False`) — no edge, no
  leak.
- **🟡 Kelly CI.** `summary` bootstrapped the mean of per-bet returns `pnl/stake`, which is
  stake-invariant, so flat and Kelly reported bit-identical CIs. **Replaced** with
  `bootstrap_yield_ci`, which resamples whole bets and recomputes the stake-weighted
  `sum(pnl)/sum(stake)`; Kelly now gets its own (wider) CI reflecting stake concentration.

## Rejected / deferred

- Reviewer's alternative placebo fix (block-shuffle within odds/selection buckets): the parametric
  market-implied Bernoulli null was chosen instead — more principled and directly interpretable
  against CLV, with no arbitrary bucket boundaries.
- **D1 (trial log + DSR/PBO on the config search) remains open.** The reviewer noted only ONE config
  was ever run, so the (negative) result is not cherry-picked; but `threshold`/`min_train`/`half_life`
  are hardcoded and ξ was never tuned (D9). Findings must be reported as "no edge under this untuned
  config" until D1 closes.

## Consequences

- `backtest/placebo.py` now exposes `market_null_test`; `engine._closing_probs` promoted to public
  `closing_probs`; `scripts/run_backtest.py` reports `market_null`.
- Lower-severity reviewer items tracked for later: same-day Kelly settled sequentially (not joint
  Kelly, D10); Shin→proportional de-vig fallback is silent (should be counted); odds-provenance is a
  filter, not a physical split.
