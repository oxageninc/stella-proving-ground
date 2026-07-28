"""Is the run still measuring anything, or has the provider gone away?

series-003 died without noticing: the connection to OpenRouter failed on trial
59 of 990 and never came back, and the harness carried on for another 500
trials at one to two seconds each, writing every one to `results.jsonl` as an
aborted, zero-model-call failure. The process exited 0. The scoreboard scored
it. Treatment E0 read 43/60 and every other arm-epoch read 0/60 — which is
indistinguishable, in the output, from a catastrophic treatment effect.

`guard-budget.sh` already made this argument: "a series that runs out of credit
mid-epoch turns provider errors into task failures, which reads as the agent
suddenly collapsing". It only ever watched the balance. An outage produces the
same corruption for free, and nothing was looking.

Run as a script by `scripts/guard-provider.sh`; importable so the rule is
testable rather than buried in a shell heredoc.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: Consecutive dead trials that mean the network, not the agent. Twelve is a
#: little over one full concurrency wave at the default of 10, so a single
#: unlucky batch cannot trip it.
DEFAULT_STREAK = 12


def is_dead_trial(row: dict) -> bool:
    """A trial that failed without the model ever being reached.

    All three conditions together, because each alone has an innocent reading:
    a genuine agent failure has model calls behind it, a stuck-loop abort has a
    different reason recorded, and only a dead transport has *no* calls, an
    abort, and a transport error at once.
    """
    return (
        row.get("status") != "completed"
        and int(row.get("model_calls") or 0) == 0
        and "transport error" in (row.get("stella_error") or "")
    )


def provider_outage(rows: list[dict], streak: int = DEFAULT_STREAK) -> bool:
    """True when the last `streak` trials were all dead in that sense."""
    if streak <= 0 or len(rows) < streak:
        return False
    return all(is_dead_trial(r) for r in rows[-streak:])


def load_tolerant(path: Path) -> list[dict]:
    """Read results.jsonl while it is being appended to.

    The final line may be half-written when the guard reads it. A torn read is
    not an outage, so it is skipped rather than treated as either signal.
    """
    rows: list[dict] = []
    try:
        text = path.read_text()
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def main(argv: list[str]) -> int:
    """Exit 0 when the provider looks dead — the shell guard's kill signal."""
    path = Path(argv[1])
    streak = int(argv[2]) if len(argv) > 2 else DEFAULT_STREAK
    return 0 if provider_outage(load_tolerant(path), streak) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
