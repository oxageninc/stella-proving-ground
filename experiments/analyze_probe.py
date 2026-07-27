"""Score the precision probe: does recall precision matter, or is presence enough?

Reads `results/precision-probe/results.jsonl` (the 2x2 of arms, one digest) and
reports the two contrasts that carry the verdict, with bootstrap intervals over
TASKS — the resampling unit that decides the width, because a task is the thing
that varies. Resampling trials instead would report a confidence the design does
not have.

Two outcome scales, deliberately both:

* **task pass** — all ~5 checks held. The headline, and the coarse one: it moves
  only when a trial crosses from "one convention missed" to "none missed".
* **check rate** — the fraction of named checks that held. The instrument this
  repo was rebuilt to have. A treatment that fixes one convention out of four
  shows up here and is invisible above.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proving_ground.stats import bootstrap_ci  # noqa: E402

ARMS = ("control", "oracle", "diluted", "noise")
ROOT = Path("results/precision-probe/results.jsonl")


def load() -> list[dict]:
    return [json.loads(l) for l in ROOT.read_text().splitlines() if l.strip()]


def per_task(rows: list[dict], arm: str, value) -> dict[str, float]:
    """Mean of `value` per task for one arm."""
    acc: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["arm"] == arm:
            v = value(r)
            if v is not None:
                acc[r["task_id"]].append(v)
    return {t: statistics.mean(v) for t, v in acc.items() if v}


def check_rate(r: dict) -> float | None:
    checks = r.get("checks") or {}
    if not checks:
        return None
    return sum(bool(v) for v in checks.values()) / len(checks)


def contrast(rows: list[dict], lo: str, hi: str, value, label: str) -> None:
    a, b = per_task(rows, lo, value), per_task(rows, hi, value)
    shared = sorted(set(a) & set(b))
    if not shared:
        print(f"  {hi} - {lo}: no shared tasks")
        return
    deltas = [b[t] - a[t] for t in shared]
    point, ci_lo, ci_hi = bootstrap_ci(deltas, statistic=statistics.mean)
    crosses = ci_lo <= 0 <= ci_hi
    print(
        f"  {label:12s} {hi:>8s} - {lo:<8s} "
        f"{point:+.3f}  95% CI [{ci_lo:+.3f}, {ci_hi:+.3f}]  "
        f"{'—' if crosses else 'EXCLUDES 0'}  (n={len(shared)} tasks)"
    )


def main() -> int:
    if not ROOT.exists():
        print(f"no results at {ROOT}")
        return 1
    rows = load()
    digests = {r["config"]["task_pool_digest"] for r in rows}
    binaries = {r["config"]["stella_version"] for r in rows}

    print(f"=== precision probe — {len(rows)} trials ===")
    print(f"    pool digest {'/'.join(sorted(digests))}  binary {'/'.join(sorted(binaries))}")
    if len(digests) > 1:
        print("    WARNING: mixed task-pool digests — arms are not comparable.")

    print("\n--- per arm ---")
    print(f"  {'arm':10s} {'trials':>7s} {'task pass':>10s} {'check rate':>11s} "
          f"{'destroyed':>10s} {'cost':>8s}")
    for arm in ARMS:
        sub = [r for r in rows if r["arm"] == arm]
        if not sub:
            continue
        passes = statistics.mean([bool(r["passed"]) for r in sub])
        checks = [check_rate(r) for r in sub]
        checks = [c for c in checks if c is not None]
        chk = statistics.mean(checks) if checks else float("nan")
        dead = sum(bool(r.get("destroyed_workspace")) for r in sub)
        cost = sum(r["cost_usd"] for r in sub)
        print(f"  {arm:10s} {len(sub):>7d} {passes:>10.3f} {chk:>11.3f} "
              f"{dead:>10d} {cost:>7.2f}$")

    # The 2x2, read in the order the questions have to be answered.
    passed = lambda r: float(bool(r["passed"]))  # noqa: E731
    present = {a for a in ARMS if any(r["arm"] == a for r in rows)}

    questions = [
        ("do the facts help at all?", "control", "oracle"),
        ("do the process notes help at all?", "control", "noise"),
        ("does adding notes to facts help?", "oracle", "diluted"),
        ("does adding facts to notes help?", "noise", "diluted"),
        ("facts vs notes, head to head", "oracle", "noise"),
        ("everything vs nothing", "control", "diluted"),
    ]
    for label, lo, hi in questions:
        if lo not in present or hi not in present:
            continue
        print(f"\n--- {label} ({hi} vs {lo}) ---")
        contrast(rows, lo, hi, passed, "task pass")
        contrast(rows, lo, hi, check_rate, "check rate")

    print(f"\n  NOTE: {len(questions)} contrasts computed. At alpha=0.05 the")
    print("  family-wise error rate is ~26%, so one interval excluding zero by")
    print("  chance is expected. Replication decides, not this table.")

    print("\n--- failure modes (where the mechanism lives) ---")
    print(f"  {'arm':10s} {'aborted':>8s} {'stuck-loop':>11s} {'step-cap':>9s} "
          f"{'req-arg':>8s} {'calls':>7s}")
    for arm in ARMS:
        sub = [r for r in rows if r["arm"] == arm]
        if not sub:
            continue
        ab = sum(1 for r in sub if r.get("status") == "aborted")
        loop = sum(1 for r in sub if "stuck-loop" in (r.get("stella_error") or ""))
        cap = sum(1 for r in sub if "step cap" in (r.get("stella_error") or ""))
        # The oracle-only signature: a convention enforced where it does not belong.
        req = sum(1 for r in sub if "missing required argument" in (r.get("detail") or ""))
        calls = statistics.mean([r["model_calls"] for r in sub])
        print(f"  {arm:10s} {ab:>8d} {loop:>11d} {cap:>9d} {req:>8d} {calls:>7.1f}")

    print("\n--- per task, check rate ---")
    cols = {a: per_task(rows, a, check_rate) for a in ARMS}
    tasks = sorted(set().union(*(set(c) for c in cols.values())))
    shown = [a for a in ARMS if cols[a]]
    print("  " + f"{'task':24s}" + "".join(f"{a:>9s}" for a in shown))
    for t in tasks:
        vals = [cols[a].get(t) for a in shown]
        cells = "".join(f"{v:>9.2f}" if v is not None else f"{'-':>9s}" for v in vals)
        print(f"  {t:24s}{cells}")

    print(f"\n  total cost: ${sum(r['cost_usd'] for r in rows):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
