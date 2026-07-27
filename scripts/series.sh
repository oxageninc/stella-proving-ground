#!/usr/bin/env bash
# Run one measurement series under a budget guard. THIS SPENDS MONEY.
set -euo pipefail

ROOT="${ROOT:?ROOT must be set}"
PY="${PY:-python3}"
EPOCHS="${EPOCHS:-2}"
TRIALS="${TRIALS:-5}"
BLOCK_SIZE="${BLOCK_SIZE:-5}"
CONCURRENCY="${CONCURRENCY:-10}"
ARMS="${ARMS:-treatment,control,sham}"
BUDGET_FLOOR="${BUDGET_FLOOR:-2.00}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cost and duration are derived from the pool that will actually run, not from
# a hardcoded task count — the pool has changed size twice, and a stale
# estimate is how a run silently costs three times what was budgeted.
read n_tasks n_arms est_usd est_min <<<"$("$PY" -c "
import sys; sys.path.insert(0,'.')
from proving_ground.tasks import load_pool
tasks = len(load_pool('evaluation')) + len(load_pool('experience'))
arms = len([a for a in '$ARMS'.split(',') if a.strip()])
trials = $EPOCHS * arms * tasks * $TRIALS
print(tasks, arms, f'{trials * 0.026:.2f}', int(trials * 110 / $CONCURRENCY / 60))
")"

echo ""
echo "==> series $(basename "$ROOT"): $EPOCHS epochs, k=$TRIALS, arms=$ARMS"
echo "    $n_tasks tasks x $n_arms arms — roughly \$$est_usd and ${est_min} min at concurrency $CONCURRENCY"
echo "    stopping if credit falls below \$$BUDGET_FLOOR"
echo ""

mkdir -p "$ROOT"

"$HERE/guard-budget.sh" "$BUDGET_FLOOR" &
guard=$!
trap 'kill "$guard" 2>/dev/null || true' EXIT

# `tee` must not swallow a non-zero exit from the run: pipefail is set above,
# so the pipeline reports the runner's status, not tee's.
"$PY" -u -m proving_ground.cli run \
  --root "$ROOT" \
  --epochs "$EPOCHS" \
  -k "$TRIALS" \
  --block-size "$BLOCK_SIZE" \
  --concurrency "$CONCURRENCY" \
  --arms "$ARMS" \
  2>&1 | tee "$ROOT/run.log"

echo ""
echo "==> done. scoreboard: $ROOT/SCOREBOARD.md"
echo "    ONE series is not a result — run 'make confirm' before believing the"
echo "    sign. This repo's own effect flipped three times."
