# `data/` — committed derived artifacts

Everything in here is **computed by this repo**, never fetched source data. Raw
football-data.co.uk season CSVs are "for match prediction only" and are not redistributable;
they live in the gitignored `.cache/` and are re-fetched by `scripts/ingest.py`. What is
committed here is the harness's own record of what it tried and what happened — the part that
has to survive a clone for the results to mean anything.

> Paper stakes only. No real money is ever staked, and nothing in this directory represents a
> real bet, a real account or a real position.

## `trial_log.jsonl` — every configuration ever run (council D1)

Append-only, one JSON object per line. Written unconditionally by `scripts/run_backtest.py` and
once per distinct config by the forward loop; backfilled for the pre-log history by
`scripts/backfill_trial_log.py`.

| field | meaning |
| --- | --- |
| `trial_id` | `sha256[:12]` of the canonical config — same config, same id |
| `logged_at` | ISO-8601 UTC timestamp of the run |
| `kind` | `backtest` (headline run) · `slice` (subgroup cut) · `forward` (paper loop config) |
| `config` | the full parameter set the run used |
| `metrics` | headline metrics, including the per-bet `sharpe` the DSR hurdle consumes |
| `code_version` | git commit the run used, or `unknown` |
| `backfilled` | `true` = reconstructed from the written record, not observed live |
| `note` | free-text provenance |

Why it exists: whoever tries N configurations and reports the best has found a maximum, not an
edge. `src/matchscout/evaluation/dsr.py` deflates the significance bar by the number of distinct
entries here, so searching harder makes claiming an edge harder. See ADR 0003.

## `bets.jsonl` — the forward paper-bet ledger

Append-only **event log**: one line per state a bet has been in. A bet is written when it is
placed (`pending`) and again when it settles (`settled` / `void`); the current state of a bet is
its last line, and the placement line stays readable forever. Columns are
`matchscout.forward.ledger.BET_COLUMNS`:

| field | meaning |
| --- | --- |
| `bet_id` | `"<match_id>\|<market>\|<selection>"` — one paper bet per fixture-market-selection, forever |
| `match_id` | `"<competition>:<season>:<YYYYMMDD>:<home>:<away>"`, as the ingest builds it |
| `market` / `selection` | `1x2` (`H`/`D`/`A`) or `ou25` (`over`/`under`) |
| `book` / `odds_taken` | the book the price came from and the decimal price taken |
| `p_model` / `edge` | model probability and `p_model * odds - 1` at placement |
| `stake` | flat paper units (0 for `no_odds` rows) |
| `timestamp_known` | when the bet was decided — always before kickoff, by construction |
| `status` | `pending` · `settled` · `void` (no result in time) · `no_odds` (predicted, no price — never an invented one) |
| `won` / `pnl` / `settled_at` | filled at settlement |
| `clv_book` / `p_close` / `clv` / `clv_beat` | closing-line value: which closing book was available, its de-vigged probability, and `p_close * odds_taken - 1` |
| `run_id` / `trial_id` | which loop run placed it, under which logged config |
| `note` | free text (e.g. why a bet was voided) |

## `bankroll_snapshots.jsonl` — one row per forward run

Append-only. Bankroll, settled/pending counts, running yield and CLV at that moment. Flat
staking is order-independent, so the curve can be rebuilt from `bets.jsonl` alone — the snapshots
exist so the dashboard has a cheap, monotone time series and so gaps in the cron are visible.

## `odds_gap_report.json` — pre-match vs. closing price movement (council D7)

Written by `scripts/analyze_odds_gap.py`. Quantifies how far prices move between the pre-match
price the harness takes and the closing price it is measured against. If prices barely move in a
segment, CLV is a weak yardstick there and the report says so.
