# match-scout — autopilot log

One line per iteration. Newest last.

- 2026-07-05 — Phase 0 scaffold: uv project (pandas/numpy/pyarrow/httpx/typer), ruff
  `E/F/I/UP/B/SIM`, pytest, MIT LICENSE, `.gitignore` (raw CSVs excluded), `betting-methodology-
  reviewer` subagent (sonnet). Gate green (1 test, ruff clean). Repo on `autopilot/work`, noreply
  email set, `main` unborn. Next: design docs, then Phase 1 data layer.
- 2026-07-05 — Design docs: spec (`docs/superpowers/specs/2026-07-05-match-scout-design.md`),
  PROJECT.md (decisions register + open inputs), PLAN.md (Phases 0–9 backlog), LOOP.md. Data-source
  facts verified (football-data.co.uk odds/closing columns, football-data.org free tier, The Odds
  API). Scope corrections locked: BTTS dropped (no free odds), CL/WM shadow-mode, DFB-Pokal parked.
  Next: SOTA self-challenge (council) → ADR 0001, then Phase 1.
- 2026-07-05 — Phase-0→1 self-challenge: 3-model council (Opus red-team, Sonnet practitioner,
  Sonnet contrarian — Fable member died on a usage-credit limit, re-run on Sonnet). Verdict:
  modify-not-pivot. Findings → ADR 0001 (D1–D11) and folded into spec + PLAN + reviewer: whole-
  harness anti-overfit incl. subgroup-slice trials (D1), CI-vs-baseline verdict + CLV beat-rate
  (D2), placebo/odds-provenance guards replace the powerless shift-test (D3), settle at taken price
  (D4), Bet365 pricing + Pinnacle-closing CLV, never Max/Avg (D5), Shin de-vig single selection path
  (D6), odds-timestamp check to Phase 1 (D7), per-era columns + 1X2-from-2013/14 window (D8),
  independent-Poisson+τ / ξ-tuning / cold-start shrinkage / penaltyblog cross-check (D9), flat-stake
  headline + Kelly/accumulator demoted (D10), cite Winkelmann/Wilkens (D11). No code change; gate
  still green. Next: Phase 1 — provider seam + fakes.
- 2026-07-05 — Phase 1 (1/n): canonical `matches`/`odds` schema (`data/schema.py`: Market/Selection/
  MatchStatus enums + `validate_matches`/`validate_odds` enforcing no-lookahead `timestamp_known ≤
  timestamp_event`, market/selection consistency, decimal odds > 1.0) + provider seam
  (`data/provider.py`: `MatchProvider`/`OddsProvider` Protocols) + `data/fakes.py` FakeProvider.
  13 new tests, gate green (14 total). Next: football-data.co.uk fetcher with per-era column mapping
  (D8) on recorded CSV fixtures from both schema eras.
- 2026-07-05 — Phase 1 (2/n): `data/football_data_co_uk.py` — pure `parse()` mapping raw season CSVs
  → canonical matches+odds, handling BOTH schema eras (D8: `Bb`-aggregates ≤2018/19 vs flat
  `Avg`+full closing suite 2019/20+), extracting B365 (price taken), PS/PSC (CLV ref), Avg (bound)
  per D5; deterministic per-file date-format parse (fixed a dateutil warning in self-review); drops
  missing/malformed odds. Tested with synthetic both-era frames (real column names, fabricated data
  — raw CSVs not redistributable). 6 new tests, gate green (20 total). Next: httpx fetch + `.cache/`
  read-through, then D7 odds-timestamp check.
- 2026-07-05 — Phase 1 (3/n): httpx fetcher + read-through `.cache/` cache (`fetch_raw` with
  injectable client + retry/backoff), `FootballDataCoUk` provider, `scripts/ingest.py` typer CLI.
  Tests via `httpx.MockTransport` (no live network in suite): fetch→cache, cache-read-no-network,
  retry-then-success, retry-exhausted, unknown-competition. 5 new tests, gate green (25 total).
  VERIFIED LIVE against real data: ingested Top-5 × {2324 flat, 1718 Bb} → 3578 matches / 78,023
  odds rows, schema-valid, 0 lookahead, Pinnacle-closing in both eras (D8 confirmed on real data).
  Match counts sanity-correct (D1=306/18-team, F1 2324=306 post-reduction, F1 1718=380). Phase 1
  data ingestion is end-to-end runnable. Next: D7 odds-timestamp check, then Phase 2 goal model.
- 2026-07-05 — Phase 2 (1/n): base independent-Poisson goal model (`model/poisson.py`:
  `score_matrix` builds the renormalized score-probability matrix; `market_probs` reads off
  1X2 + O/U2.5). This is the ρ=0/no-time-decay ablation core (D9); Dixon-Coles will add τ +
  time-decay on top. numpy-only (no scipy yet — added when MLE fitting lands). 10 new tests
  incl. analytic known-value checks, gate green (35 total). Next: fit team attack/defence + home
  advantage (scipy MLE) on pre-matchday data, then the τ correction + time-decay (full DC).
- 2026-07-05 — Phase 2 (2/n): `model/goal_model.py` — `GoalModel` + `fit_poisson` MLE fit (scipy
  L-BFGS-B) of per-team attack/defence + global home-advantage + base rate, with ridge shrinkage
  resolving identifiability + serving as promoted-team shrinkage (D9). Added scipy dep. Deterministic
  (zero-init). 8 new tests (strength recovery on synthetic league, determinism, error cases). Gate
  green (43 total). VERIFIED on real E0 2023/24: top attack Man City/Arsenal/Newcastle/Liverpool,
  best defence Arsenal, home_adv +0.20 — recovers the real season. Next: τ low-score correction +
  exponential time-decay (full Dixon-Coles), then calibration vs the closing line.
- 2026-07-05 — Phase 2 (3/n): full Dixon-Coles — `fit_dixon_coles` adds the τ low-score correction
  (fitted ρ, bounded ±0.2 to keep τ>0) + exponential time-decay (half-life + as-of weighting) atop
  the base fit, sharing `_fit`; `_apply_tau` corrects + renormalizes the score matrix in `predict`.
  `fit_poisson` stays the ρ=0/no-decay ablation. 3 new tests (ρ bounds, τ renorm/shift, time-decay
  up-weights recent form). Gate green (46 total). Next: walk-forward calibration eval (reliability +
  Brier + log-loss vs closing-line-implied), and tune ξ on held-out data (not hardcoded).
- 2026-07-05 — Phase 2 (4/n): `evaluation/metrics.py` — `brier_score` + `log_loss` (multiclass,
  strictly-proper) + `reliability_curve` (binary calibration bins). The honesty-critical scoring
  building block for model calibration, backtest, and ML. 7 new tests, gate green (53 total). Next:
  Shin/proportional de-vig (D6) to build the closing-line benchmark, then the walk-forward
  calibration eval (Dixon-Coles vs the market) + ξ tuning.
- 2026-07-05 — Phase 3 (de-vig, D6): `value/devig.py` — `booksum`, `devig_proportional`, and
  `devig_shin` (Shin insider-model via brentq, falls back to proportional if unbracketed).
  Favourite-longshot correction verified (Shin lifts favourites, trims longshots vs proportional);
  fair-market recovery + two-way market tested. 7 new tests, gate green (60 total). Next: walk-
  forward calibration eval — Dixon-Coles predictions vs the Shin-de-vigged Pinnacle-closing line
  (Brier/log-loss/reliability), on the real cached data; then tune ξ.
- 2026-07-05 — Phase 2 (5/n) MILESTONE: leakage-safe `walk_forward_predict` (per-matchday fit on
  the past only; no-lookahead proven by test) + `calibration.py` (model vs Shin-de-vigged Pinnacle
  closing, Brier/log-loss, rule-generated verdict) + `scripts/eval_model.py`. 11 new tests, gate
  green (68 total). FIRST REAL FINDING on E0 2022/23–2023/24 (675 matches, min_train 80): model
  Brier 0.570 / log-loss 0.965 vs market 0.547 / 0.930 → model does NOT beat the closing line
  (expected, honest). The harness now measures the real thing. Next: ξ tuning on held-out data;
  then Phase 3 edge/value-selection (EV on Bet365 price) + Phase 4 backtest engine.
- 2026-07-05 — Phase 3 (edge): `value/edge.py` — `edge` (EV per unit) + `select_value_bets` (SOLE
  selection path, D6: EV on Bet365 pre-match price, D5; ignores closing/other-book odds; sorted by
  edge). 6 new tests, gate green (74 total). Next: Phase 4 backtest engine — settle value bets at
  the taken price (D4), flat + Kelly staking, CLV, CI-vs-baseline verdict, placebo + odds-provenance.
- 2026-07-05 — Phase 4 (staking/engine/metrics/baselines + CLI): `backtest/staking.py` (flat +
  fractional-Kelly, edge-shrink, per-bet cap), `backtest/engine.py` (settle at taken price, bankroll,
  CLV vs Pinnacle closing), `backtest/metrics.py` (yield-with-bootstrap-CI, drawdown, CLV beat-rate,
  CI-vs-0 verdict), `backtest/baselines.py`, `scripts/run_backtest.py`. 26 new tests, gate green (100
  total). CORE MILESTONE — real value-betting backtest E0 2022/23–2023/24: 971 value bets (edge>5%),
  flat yield −4.7% (CI [−13.0%,+4.1%] straddles 0), CLV mean −5.4%, CLV beat-rate 20.4% → NO edge;
  the model's value bets have NEGATIVE CLV (it bets against the sharp close and loses) — the expected
  honest finding, exactly what the harness exists to show. Baselines flat: home +1.0/fav +0.9/over
  −0.7%. Ran `betting-methodology-reviewer` (D-requirement) before finalizing. Open (D1): trial log +
  DSR/PBO on the knob search; open (D3): label-permutation/placebo test. Next: fold reviewer findings,
  then Phase 5 ML challenger.
- 2026-07-05 — Phase 4 (D3 placebo): `backtest/placebo.py` — label-permutation test (shuffle
  outcomes, re-settle), detects a guaranteed-win leak in tests; wired into `run_backtest.py`. 2 new
  tests, gate green (102 total). Placebo on real E0 2022/23–2023/24: real yield −4.7% vs placebo mean
  +18.8% (real_exceeds_95pct=False) → reinforces NO positive edge; the model's picks do worse than
  random outcomes (anti-selection at the margin, consistent with −5.4% CLV). NOTE: the large real-vs-
  placebo gap warrants interpretation (genuine anti-selection vs placebo base-rate artifact) — flagged
  for the running methodology reviewer. D1 (trial log/DSR) still open.
- 2026-07-05 — Phase 4 (review fixes, ADR 0002): `betting-methodology-reviewer` verified the headline
  clean (walk-forward leak-freedom, vig/selection, settlement-at-taken-price, CLV path) but found 🔴
  the placebo null was globally-shuffled (ignored market-implied difficulty → inflated to +18.8%) and
  🟡 the Kelly CI was stake-invariant (flat==Kelly bit-for-bit). FIXED both: `market_null_test` draws
  each bet's outcome from the de-vigged closing prob (centers at CLV); `bootstrap_yield_ci` resamples
  stake-weighted yield. Re-run confirms: null mean −5.45% ≈ CLV −5.36%, real −4.7% inside
  (real_exceeds_null_95pct=False), Kelly CI now differs from flat. 1 net new test, gate green (103).
  Open: D1 trial-log/ξ-tune; low-sev: joint same-day Kelly, devig-fallback logging. Next: Phase 5 ML
  challenger (walled-off LightGBM; must beat DC AND the closing line).
- 2026-07-05 — Phase 5 (ML challenger): `ml/validation.py` (purged+embargoed WF splits),
  `ml/dataset.py` (1X2 features = DC walk-forward probs + Shin market probs), `ml/evaluate.py` +
  `scripts/run_ml.py` (LightGBM native Booster API — no scikit-learn dep — OOS scorecard vs DC vs
  market). 14 new tests, gate green (117 total). REAL FINDING E0 2022/23–2023/24 (563 OOS): ML Brier
  0.774 / log-loss 1.674 vs DC 0.563 / 0.952 vs market 0.539 / 0.917 → ML beats NEITHER; naive GBDT
  overfits the small free-data sample (log-loss worse than uniform) and loses to the statistical
  baseline — the honest negative result (signal-trader pattern). Phases 0–5 complete. Next: Phase 6
  forward paper loop, then CI/dashboard/publish.
- 2026-07-05 — football-data.org integration (Nico provided the free API key): secret stored in
  `.env` (gitignored, NEVER committed; `.env.example` + `config.py` .env loader added),
  `data/football_data_org.py` (CL/WC/EC fixtures+results → canonical matches, no odds → shadow-mode,
  X-Auth-Token, injectable client, retry on rate-limit). Fixed a tz-compare bug in
  `schema.validate_matches` (UTC-normalize; org times are real UTC). 9 new tests (MockTransport, no
  live key needed), gate green (126 total). LIVE-VERIFIED with the real key: WC 2026 = 104 matches
  (90 played / 14 scheduled — tournament in progress), CL 2024/25 = 189 (PSG 5-0 Inter final present).
  NOTE: producing CL/WC *predictions* needs a cross-competition pooled rating model (Phase 6); WC is
  limited — national teams aren't in the club-league model's team set. Next: ingest CLI for org
  competitions, then the cross-competition model + shadow-mode predictions.
- 2026-07-05 — Shadow-mode tips (Nico: "CL + WM tips, esp. WM"): `tips.py` (`fixture_tips`:
  fit Dixon-Coles on played org history, predict scheduled fixtures → 1X2 + O/U probs + pick +
  most-likely score) + `most_likely_score` + `scripts/tips.py` CLI. 5 new tests, gate green (130).
  Key insight: fit WM on international matches, CL on org club data — org names are self-consistent,
  so NO cross-source (co.uk↔org) team-name reconciliation needed. LIVE WM 2026: 7 tips for the
  remaining known-team matches (Brazil-Norway, Mexico-England, Portugal-Spain, USA-Belgium,
  Argentina-Egypt, Switzerland-Colombia, France-Morocco); semis/final skipped (TBD teams). CAVEAT:
  thin int'l data → overconfident probabilities (Brazil 98%); directional shadow tips, honestly
  labelled, NOT calibrated like the league backtest. CL: machinery works but off-season (no upcoming
  fixtures until the 2026/27 draw). Next: (offer) stronger shrinkage for thin-data tips; GitHub
  Actions live loop needs Nico's remote + secret.
- 2026-07-05 — Markets layer + richer tips (Nico: all O/U lines, combos, qualification distinction,
  "research Bet365"). Researched Bet365 markets (subagent) → confirmed goals-only markets are
  derivable, goalscorer/cards/corners need player/event data (out), outright needs bracket sim.
  Built `model/markets.py` (all O/U lines, BTTS, correct-score top-N, double-chance, and `to_advance`
  = knockout qualify via ET+penalties, distinct from 90-min 1X2), exposed `GoalModel.score_matrix`
  (τ-corrected), rebuilt `tips.py` (full goals board + `suggest_combo`) + CLI. 13 new tests, gate
  green. LIVE WM 2026: rich board incl. the qualification insight (Portugal–Spain: draw 69% in 90'
  but Spain 67% to ADVANCE). Goalscorer markets: HONEST NO (no player data). Combos labelled −EV.
  Offered next: bracket Monte-Carlo for "to win the World Cup" outrights; still-open: thin-data
  overconfidence (stronger shrinkage), two-legged CL tie modelling.
- 2026-07-05 — Phase 8 dashboard (Nico chose: match-scout's own React dashboard + portfolio tile):
  `scripts/export_site.py` writes static JSON (WM tips + backtest story + bankroll curve) to
  `site/public/data/`; React 19 + Vite + TS app in `site/` (App + Disclaimer + HonestHarness +
  hand-rolled SVG BankrollChart + TipsBoard), base `/match-scout/` for Pages, reads static JSON via
  `import.meta.env.BASE_URL`. `npm run build` green (tsc strict + vite); preview verified serving
  index + data JSON + JS bundle (all 200). No FastAPI (YAGNI — static export). node_modules + dist
  gitignored. STILL OPEN: portfolio tile needs the LIVE URL → blocked on Nico's remote + Pages
  deploy; local view via `npm --prefix site run dev`.
