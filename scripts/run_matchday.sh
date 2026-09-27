#!/usr/bin/env bash
# One matchday tick: advance the forward paper loop, then rebuild the pages from the ledgers.
#
# Paper stakes only. Safe to run any number of times a day — placement is keyed by
# fixture-market-selection and settlement only touches pending bets, so a repeat is a no-op.
#
# Registered in the user crontab (see README "Jeden Spieltag"):
#   47 8,17 * * * flock -n /tmp/match-scout-forward.lock \
#     ~/private/match-scout/scripts/run_matchday.sh \
#     >> ~/private/match-scout/logs/forward.log 2>&1
#
# It writes data/*.jsonl and site/public/ but never commits: an unattended commit on whatever
# branch happens to be checked out is exactly the accident the git rules forbid.
#
# NOT set -e: a failed loop run must not stop the page rebuild from the ledgers already on disk.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"
cd "$REPO_DIR" || exit 1
mkdir -p logs

echo "=== $(date -Is) matchday run (branch $(git branch --show-current 2>/dev/null || echo '?'))"
failed=0

if "$UV" run --quiet python scripts/run_forward.py > logs/last_forward.json; then
  "$UV" run --quiet python - <<'PY'
import json
d = json.load(open("logs/last_forward.json"))
keys = ("n_predicted", "n_placed", "n_no_odds", "n_settled_now", "n_predictions_settled_now")
print("forward:", {k: d.get(k) for k in keys}, "| skipped:", d.get("skipped_competitions"))
PY
else
  echo "forward loop FAILED — see logs/last_forward.json"
  failed=1
fi

"$UV" run --quiet python scripts/spieltag.py || failed=1
exit "$failed"
