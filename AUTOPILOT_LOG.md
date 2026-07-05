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
