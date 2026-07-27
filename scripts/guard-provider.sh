#!/usr/bin/env bash
# Stop a series when the provider stops answering, rather than recording the
# outage as hundreds of failed trials.
#
# This is not hypothetical. series-003 died exactly this way: the connection to
# OpenRouter failed on trial 59 of 990 and never recovered, and the harness
# carried on for another 500 trials at one to two seconds each, writing every
# one of them to results.jsonl as an aborted, zero-model-call failure. The run
# exited 0. The scoreboard scored it. Treatment E0 read 43/60 and every other
# arm-epoch read 0/60, which looks exactly like a catastrophic treatment effect
# and is actually a dead socket.
#
# guard-budget.sh already carries the argument for why this matters — "a series
# that runs out of credit mid-epoch turns provider errors into task failures,
# which reads as the agent suddenly collapsing" — but it only ever watched the
# balance. An outage produces the identical corruption while the balance sits
# untouched, and nothing was looking.
#
# The rule lives in proving_ground/health.py so it is testable rather than
# buried in a heredoc; `make smoke` covers it.
set -uo pipefail

ROOT="${1:?ROOT must be set}"
STREAK="${2:-12}"
PY="${PY:-python3}"
RESULTS="$ROOT/results.jsonl"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while pgrep -f 'proving_ground.cli run' >/dev/null 2>&1; do
  if [ -f "$RESULTS" ] && (cd "$HERE" && "$PY" -m proving_ground.health "$RESULTS" "$STREAK"); then
    echo ""
    echo "==> PROVIDER DOWN — last $STREAK trials aborted with a transport error"
    echo "    and zero model calls. Stopping: every further trial would be"
    echo "    recorded as a failure indistinguishable from a result."
    pkill -f 'proving_ground.cli run' || true
    sleep 2
    pkill -f 'stella run' || true
    break
  fi
  sleep 20
done
