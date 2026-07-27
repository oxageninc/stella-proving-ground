#!/usr/bin/env bash
# Kill a running series before the account empties rather than after.
#
# A series that runs out of credit mid-epoch turns provider errors into task
# failures, which reads as the agent suddenly collapsing — strictly worse than
# a shorter series, because the failure is indistinguishable from a result.
set -uo pipefail

FLOOR="${1:-2.00}"
PY="${PY:-python3}"

read_credit() {
  curl -s -H "Authorization: Bearer ${OPENROUTER_API_KEY:-}" \
       https://openrouter.ai/api/v1/credits 2>/dev/null \
    | "$PY" -c "import json,sys;d=json.load(sys.stdin)['data'];print('%.2f'%(d['total_credits']-d['total_usage']))" 2>/dev/null
}

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "==> no OPENROUTER_API_KEY; budget guard disabled"
  exit 0
fi

while pgrep -f 'proving_ground.cli run' >/dev/null 2>&1; do
  rem=$(read_credit)
  # An unreadable balance must not kill a paid run — only a balance we can
  # actually read, and that is genuinely below the floor, is grounds to stop.
  if [ -n "$rem" ] && "$PY" -c "import sys;sys.exit(0 if float('$rem') < $FLOOR else 1)"; then
    echo ""
    echo "==> BUDGET FLOOR (\$$rem left) — stopping the series"
    pkill -f 'proving_ground.cli run' || true
    sleep 2
    pkill -f 'stella run' || true
    break
  fi
  sleep 45
done
