"""Compact finding-level readout of a series, on every outcome.

`proving_ground.scoreboard` renders the full page. This prints the part a
finding is written from: the per-arm means, the two contrasts that carry the
verdict (treatment−control, treatment−sham) on all five outcomes at every
epoch, and — the thing a single epoch cannot show — whether the direction
*holds across epochs* or wanders.

That last column is the point. This repo's headline effect has flipped sign
three times, and a 12-task bootstrap at one epoch has repeatedly produced a
confident interval that did not survive being run again. Three epochs give
three semi-independent looks at the same contrast; a real effect should point
the same way in all of them.

    python3 experiments/analyze_series.py results/series-003
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proving_ground.stats import (  # noqa: E402
    CONTINUOUS_OUTCOMES,
    family_wise_error,
    load_results,
    paired,
    paired_outcome,
    summarize,
)

ARMS = ("treatment", "control", "sham")
PAIRS = (("treatment", "control"), ("treatment", "sham"))


def _f(x: float, spec: str) -> str:
    return "—" if x != x else format(x, spec)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "results/series-003")
    path = root / "results.jsonl"
    if not path.exists():
        print(f"no results at {path}")
        return 1

    rows = load_results(path)
    summary = summarize(rows)
    if not summary:
        print("no scorable arm-epochs — every cell failed the full-coverage check")
        return 1

    epochs = sorted({e for (_, e) in summary})
    cfg = rows[0].get("config", {})
    digests = {r.get("config", {}).get("task_pool_digest") for r in rows}
    binaries = {r.get("config", {}).get("binary_sha256") for r in rows}

    print(f"=== {root.name} — {len(rows)} trials, epochs {epochs} ===")
    print(f"    stella {cfg.get('stella_version')} ({str(cfg.get('stella_commit'))[:8]})")
    print(f"    pool {'/'.join(sorted(str(d) for d in digests))}  "
          f"binary {'/'.join(sorted(str(b)[:16] for b in binaries))}")
    if len(digests) > 1 or len(binaries) > 1:
        print("    WARNING: mixed pool digest or binary — arms are not comparable.")

    # ------------------------------------------------------------ per arm
    print("\n--- per arm, per epoch (evaluation pool only) ---")
    print(f"  {'arm':10s} {'ep':>3s} {'trials':>7s} {'compl':>6s} {'acc':>6s} "
          f"{'calls':>7s} {'cost':>8s} {'out tok':>8s} {'stuck':>6s}")
    for arm in ARMS:
        for e in epochs:
            s = summary.get((arm, e))
            if not s:
                continue
            m = s.outcome_mean
            print(f"  {arm:10s} {e:>3d} {s.trials:>7d} {s.completed:>6d} "
                  f"{s.accuracy:>6.3f} {m['model_calls']:>7.1f} "
                  f"{m['cost_usd']:>8.4f} {m['output_tokens']:>8.0f} "
                  f"{m['stuck_loop']:>6.3f}")

    # ------------------------------------------------------- the contrasts
    n = 0
    consistency: dict[tuple[str, str, str], list[float]] = {}
    for arm_a, arm_b in PAIRS:
        print(f"\n--- {arm_a} − {arm_b} ---")
        print(f"  {'outcome':16s} {'ep':>3s} {'delta':>10s} {'95% CI':>22s} "
              f"{'rel':>8s} {'n':>3s}  verdict")
        for label, key, spec in (
            ("task pass", None, "+.3f"),
            *[(o.label, o.key, "+" + o.fmt) for o in CONTINUOUS_OUTCOMES],
        ):
            for e in epochs:
                c = (
                    paired(summary, e, arm_a, arm_b)
                    if key is None
                    else paired_outcome(summary, e, arm_a, arm_b, key)
                )
                if not c:
                    continue
                n += 1
                consistency.setdefault((arm_a, arm_b, label), []).append(c.delta)
                ci = f"[{_f(c.lo, spec)}, {_f(c.hi, spec)}]"
                print(f"  {label:16s} {e:>3d} {_f(c.delta, spec):>10s} {ci:>22s} "
                      f"{_f(c.relative, '+.1%'):>8s} {c.n_tasks:>3d}  "
                      f"{'EXCLUDES 0' if c.significant else '—'}")

    # --------------------------------------------------------- consistency
    print("\n--- direction across epochs (the replication a single epoch cannot give) ---")
    print(f"  {'comparison':22s} {'outcome':16s} {'deltas by epoch':>28s}  sign")
    for (arm_a, arm_b, label), deltas in consistency.items():
        if len(deltas) < 2:
            continue
        # Scale-relative tolerance: an exact zero arrives as -9.25e-18 out of the
        # bootstrap, and calling that "negative" would invent a direction.
        scale = max((abs(d) for d in deltas), default=0.0)
        eps = scale * 1e-9
        signs = {d > 0 for d in deltas if abs(d) > eps}
        verdict = "consistent" if len(signs) <= 1 else "FLIPS"
        cells = " ".join(f"{d:+.4g}" for d in deltas)
        print(f"  {arm_a[:9]}−{arm_b[:9]:12s} {label:16s} {cells:>28s}  {verdict}")

    print(f"\n  {n} contrasts computed here; family-wise error at alpha=0.05 is "
          f"~{family_wise_error(n):.0%}.")
    print("  These outcomes were chosen after seeing the probe, so they are")
    print("  exploratory. Direction agreeing across epochs and across independent")
    print("  measures is what earns confidence, not any one interval.")

    total = sum(r["cost_usd"] for r in rows)
    done = sum(1 for r in rows if r.get("status") == "completed")
    print(f"\n  {done}/{len(rows)} trials completed. total cost ${total:.2f} "
          f"(${total / max(1, len(rows)):.4f}/trial)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
