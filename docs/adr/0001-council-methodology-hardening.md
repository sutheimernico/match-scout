# ADR 0001 — Council methodology hardening

**Status:** Accepted (2026-07-05)

## Context

At the Phase-0→1 boundary (per `~/private/AUTOPILOT.md` "once per phase, self-challenge / SOTA")
a 3-model council stress-tested the design (spec `2026-07-05-match-scout-design.md` + `PLAN.md`):
Opus 4.8 (methodology red-team), Sonnet 5 (football-modeling practitioner, verified claims against
the live football-data.co.uk CSVs), Sonnet 5 (contrarian + SOTA scan). The contrarian on Fable 5
died on a usage-credit limit and was re-run on Sonnet.

The verdict was **modify, not pivot**: the honest-harness foundation (point-in-time discipline,
vig-honest EV edge, closing-line-as-benchmark, purged/embargoed WF, "the finding is the finding")
is unusually rigorous for the genre and worth keeping. But the council found three 🔴 structural
defects and several 🟡 inflation channels that must be fixed before Phase 4, plus empirical data
facts that reshape Phase 1–2. Full reports are archived in the session transcript.

## Decision

Accepted changes (ID'd so the spec/PLAN can reference them):

- **D1 — Anti-overfit discipline covers the WHOLE harness, not just the ML challenger.** *(biggest
  honesty risk; Opus F1 + Sonnet + contrarian/Wilkens-2026)* The headline is the Dixon-Coles
  backtest, which has many free knobs (edge threshold, market, league, time-decay ξ, staking,
  min-odds). Requirement: pre-register the config before seeing 2019/20+ results (or split a
  design-fold from a reported holdout-fold); log **every** config the loop tries — including
  **subgroup slices** (per-league / per-market / per-selection-type) as trials — and apply a rising
  significance hurdle (Deflated-Sharpe / PBO analog) to the Dixon-Coles path too.
- **D2 — Verdict is CI-vs-baseline, not point-vs-point.** *(Opus F6 + Sonnet)* Report bootstrap /
  Wilson CIs on ROI, yield, and mean CLV; enforce a minimum bet count before any verdict; the
  rule-generated §8.2 verdict compares a CI against the closing-line baseline. Promote **CLV
  beat-rate** (fraction of bets with positive CLV) to a named headline metric alongside aggregate
  CLV%.
- **D3 — Replace the powerless shift-test with football-appropriate leak guards.** *(Opus F2)* The
  copied one-matchday-lag shift-test barely perturbs slowly-changing ratings. Replace/augment with:
  (a) a hard fit-window assertion `train.date < predict.date` (same-day excluded → hard error);
  (b) an **odds-provenance assertion** — the selection/pricing path can only read `is_closing=false`
  rows; closing columns are physically withheld until settlement; (c) a **label-permutation /
  placebo test** — shuffle outcomes and confirm ROI collapses to ≈ −vig. Shift-test demoted to a
  weak sanity check.
- **D4 — Settle strictly at the taken pre-match price; closing odds feed ONLY CLV.** *(Opus F3)*
  Remove the ambiguity that closing odds could ever be a settlement price. Drop/rename
  `is_closing_odds` on the bet row; add a test asserting every settled bet's `odds_taken` came from
  an `is_closing=false` row.
- **D5 — Bet at ONE a-priori-fixed single book; never `Max`/`Avg`.** *(Opus F4 + Sonnet F3)* `Max`
  is the best price discovered in hindsight across books (unrealizable); `Avg` assumes costless
  shopping and drifts in composition across seasons. **Price taken = Bet365 (`B365*`) pre-match**
  (single, consistently available). **CLV reference = Pinnacle closing (`PSC*`)** — football-data's
  own 88k-pair analysis makes Pinnacle-closing the sharpest efficiency benchmark. `Avg`/`Max`
  reported only as clearly-labelled optimistic bounds, never headlined.
- **D6 — Shin's-method de-vig for the benchmark, not proportional.** *(Opus F5 + contrarian ref)*
  Proportional de-vig carries a favourite-longshot bias that can manufacture a fake edge on
  longshots. Use Shin (or power/log) as default; run proportional-vs-Shin as a documented
  sensitivity check. The EV edge formula `edge = p_model*odds − 1` (on real with-vig odds) is
  **correct and the SOLE selection path** — delete the "margin-adjusted implied probability"
  wording so two selection paths cannot diverge. De-vig is used only to build the benchmark
  probability and the calibration comparison.
- **D7 — Odds-timestamp verification moves to Phase 1.** *(contrarian A1 + Opus F8)* Empirically
  measure the pre-`C` vs `C` odds gap/variance on the real CSVs (is there genuine line movement to
  capture, or is "edge vs closing" measuring noise?); confirm pre-match columns precede kickoff;
  document the `timestamp_known` imputation rule (kickoff − N h) — never set `timestamp_known =
  kickoff`.
- **D8 — Per-era column mapping + two backtest windows.** *(Sonnet F1/F2, empirically verified)*
  Aggregate columns migrate `Bb`-prefixed (≤2018/19) → flat `Max/Avg` (2019/20+). Phase 1 needs an
  explicit per-era mapping table and test fixtures from both eras. Backtest windows split by market:
  **1X2 CLV from 2013/14+** (`PSC*` present), **O/U-2.5 CLV from 2019/20+** (no earlier closing).
- **D9 — Dixon-Coles specification fixes.** *(Sonnet F4)* Correct the spec wording to **"independent
  Poisson + Dixon-Coles τ low-score correction"** (not "bivariate Poisson"). Phase-2 tests must
  assert: fitted ρ sign + reasonableness bound (small negative), goal-matrix renormalization after
  τ within a documented tolerance, a single global home-advantage constant (no per-team at v1), and
  a numeric cross-check against **penaltyblog** (offline correctness reference; adopting it as a
  runtime dependency → Needs Nico). **ξ time-decay is TUNED via held-out log-lik/Brier (walk-forward),
  never hardcoded.** **Promoted-team cold-start:** explicit shrinkage of new-team attack/defence
  toward the league mean, regularization weight decaying with match count (tested, not emergent MLE).
- **D10 — Demote Kelly + accumulator to secondary; flat-stake + calibration/CLV is the headline.**
  *(Opus F7 + contrarian A2/A3)* Kelly amplifies a noisy near-zero edge (optimizer's curse; correlated
  same-day bets break independence). Make flat-stake yield the primary, order-independent result;
  Kelly is a secondary illustrative track with wide CIs, edge shrunk before staking, joint Kelly for
  same-day bets, and a firm hard per-bet cap (≤5% bankroll). The **Wettschein/accumulator builder is
  KEPT** (Nico explicitly requested betting slips) but is explicitly framed and reported as the
  honest demonstration that accumulators compound the margin and are −EV — a secondary track, not a
  headline. The dashboard leads with the calibration/CLV verdict; bankroll/Kelly/accumulator are
  visually secondary.
- **D11 — Cite the market-efficiency literature in the honesty framing.** *(contrarian refs)*
  Winkelmann et al. (2024, "Are Betting Markets Inefficient?") and Wilkens (2026, Bundesliga
  simple-models) named in the spec/README as the sourced reason the harness treats a "profitable"
  backtest with default skepticism. Note in the ML writeup that "beats Dixon-Coles" is near-guaranteed
  and uninteresting once the ML has the market-implied-prob feature; only "beats the closing line"
  is the real test.

## Rejected / held

- **Pivot to forecasting-only** (contrarian's leaner alternative): rejected. All three converge on
  "modify, not pivot"; the betting-sim framing is the intentional signal-trader sibling. Mitigated
  by D10/D11 rebalancing emphasis toward calibration/CLV.
- **Drop the accumulator builder as YAGNI** (contrarian A3): rejected — it is a direct Nico
  requirement ("Wettscheine"). Kept but demoted and reframed per D10.
- **Chase Dixon-Coles variants (ANS / Mar-Co / Sarmanov)**: deferred to an ADR-only footnote;
  reported RPS gaps are 3rd–4th-decimal noise. Revisit only if Phase-2 calibration shows vanilla DC
  underperforming Poisson/Elo by more than noise.
- **Adopt penaltyblog / soccer_xg as dependencies**: penaltyblog is an offline cross-check only
  (dependency → Needs Nico); soccer_xg needs event-stream data outside the free-data scope.

## Consequences

- Phase 1 gains D7 (odds-timestamp data-quality check) and D8 (per-era mapping, two windows) — more
  upfront verification, less rework later.
- Phase 2 gains D9 (ρ-sign/renorm/cold-start/ξ-tuning tests + penaltyblog cross-check).
- Phase 3 changes to D5 (single-book pricing), D6 (Shin de-vig + single selection path).
- Phase 4 gains D1/D2/D3/D4 — the trial log, whole-harness DSR/PBO, CI-vs-baseline verdict, placebo
  test, odds-provenance + settlement-price assertions. This is the load-bearing honesty work.
- The `betting-methodology-reviewer` subagent prompt is updated to check: subgroup-slice trial
  counting, odds-provenance, the placebo test, Max/Avg-price rejection, and Shin de-vig.
- `PLAN.md` and the spec are edited in the same commit to reflect D1–D11.

## Addenda

- **2026-09-20 — D1 CLOSED.** Trial log + trials-adjusted DSR hurdle shipped; design-fold vs.
  holdout-fold pre-registration rule recorded. See ADR 0003. The interim caveat "no edge under
  this untuned config" is retired in favour of the measured DSR verdict.
