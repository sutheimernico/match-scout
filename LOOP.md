# match-scout — LOOP (per-iteration prompt for the autonomous build agent)

You are a fresh headless agent. You do ONE high-value thing, verify it, commit it, and exit.
Progress lives on disk (this file, `PROJECT.md`/`PLAN.md`, git history, `AUTOPILOT_LOG.md`) — never
in context.

## Per-iteration protocol

1. Read `AUTOPILOT.md` (author's global loop rules, not part of this repo) (global rules), then this `LOOP.md`, then `PLAN.md` + `PROJECT.md`.
2. Confirm you are on branch `autopilot/work` (the runner guarantees this; if not, stop).
3. Pick the SINGLE highest-value open `- [ ]` task (top-to-bottom, earlier phases first). If a phase
   boundary is reached, run the once-per-phase self-challenge/SOTA step first (write an ADR if it
   changes the plan).
4. Do that one task. Small, reviewable diff. Read existing code before writing; match conventions.
   New logic ships with a test. Network access stays behind the provider seam and is faked in tests.
5. Run the gate: `uv run pytest -q` (green) AND `uv run ruff check .` (clean). If red, fix or revert.
6. On green: commit (Conventional Commits, English, imperative), check off the task in `PLAN.md`,
   append a one-line note to `AUTOPILOT_LOG.md`. Then exit.
7. If a task needs a paid resource or a Nico-only input: move it to "Needs Nico", pick another, or
   exit. Never sign up for anything paid. Never fake data or metrics.

## Project-specific hard constraints (never override)

- **Local & free.** football-data.co.uk (no key) + football-data.org free tier (`X-Auth-Token`,
  optional). No paid feeds. No real-money anything — paper stakes only.
- **Point-in-time + vig honesty.** Only `timestamp_known` prices/selects a bet. Edges are computed
  against margin-adjusted implied probs; P&L settles at real odds. No lookahead.
- **Raw source CSVs are never committed** (license "for match prediction only"). Fetch to `.cache/`
  (gitignored); commit only derived artifacts under `data/`. Credit the source.
- **Honesty guardrails.** Every output surface carries the DISCLAIMER; benchmark = closing line
  (after vig) + naive baselines; report negative results, do not hide them.
- **Determinism in tests.** No live network in tests; use the `Fake*` provider seams.
- **Pin new deps** with a one-line justification; simplest solution that meets the task (YAGNI).

## Gate (objective done-check)

`uv run pytest -q` green + `uv run ruff check .` clean. Commit only a green gate.

## Where things are

- Spec: `docs/superpowers/specs/2026-07-05-match-scout-design.md`
- Code: `src/matchscout/` (one responsibility per file) · Tests: `tests/` · CLIs: `scripts/`
- Raw cache: `.cache/` (gitignored) · Derived artifacts: `data/` (committed by the pipeline)
- Run locally: `uv run python scripts/<name>.py`
