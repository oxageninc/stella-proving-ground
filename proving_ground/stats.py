"""Statistics — pre-registered, paired, and bootstrapped.

Three commitments, all of which cost the harness its ability to flatter itself:

* **Medians with bootstrap confidence intervals, never a single run.** LLM
  agents are noisy enough that a one-run difference is not evidence of
  anything.
* **Paired per-task comparison.** Comparing pool means throws away the fact
  that the same six tasks are run in every arm; pairing on task recovers that
  power and stops an easy task drifting between arms from moving the headline.
* **A pre-registered effect size.** An improvement inside the control arm's own
  run-to-run variance is not an improvement.

The bootstrap is seeded so a published number can be reproduced exactly.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median

BOOTSTRAP_SEED = 20260726
BOOTSTRAP_DRAWS = 10000

#: Pre-registered: the smallest treatment-minus-control difference in
#: resolution accuracy that counts as a result. Below this, we report no effect
#: regardless of what the point estimate does.
MIN_MEANINGFUL_EFFECT = 0.10


def load_results(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def evaluation_rows(rows: list[dict]) -> list[dict]:
    """Only held-out evaluation trials are ever scored.

    Experience and sham trials appear in the same file for auditability; they
    are not results and must never reach a metric.
    """
    return [r for r in rows if r.get("pool") == "evaluation"]


def bootstrap_ci(
    values: list[float],
    *,
    statistic=median,
    draws: int = BOOTSTRAP_DRAWS,
    alpha: float = 0.05,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Return (point, lo, hi) for `statistic` by percentile bootstrap."""
    if not values:
        return (float("nan"), float("nan"), float("nan"))
    if len(values) == 1:
        v = float(values[0])
        return (v, v, v)
    rng = random.Random(seed)
    n = len(values)
    draws_out = []
    for _ in range(draws):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        draws_out.append(statistic(sample))
    draws_out.sort()
    lo = draws_out[int((alpha / 2) * draws)]
    hi = draws_out[min(draws - 1, int((1 - alpha / 2) * draws))]
    return (float(statistic(values)), float(lo), float(hi))


@dataclass
class ArmEpoch:
    arm: str
    epoch: int
    trials: int
    solved: int
    accuracy: float
    accuracy_lo: float
    accuracy_hi: float
    per_task_rate: dict[str, float]
    tokens_per_solved: float
    cost_per_solved: float
    seconds_per_solved: float
    calls_per_solved: float
    recalled_tokens_per_call: float
    cited_share: float
    store_memories: int


def _safe_div(a: float, b: float) -> float:
    return a / b if b else float("nan")


def summarize(rows: list[dict]) -> dict[tuple[str, int], ArmEpoch]:
    """Per arm, per epoch: the pre-registered metric table."""
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in evaluation_rows(rows):
        grouped[(row["arm"], row["epoch"])].append(row)

    out: dict[tuple[str, int], ArmEpoch] = {}
    for (arm, epoch), trials in sorted(grouped.items()):
        by_task: dict[str, list[dict]] = defaultdict(list)
        for t in trials:
            by_task[t["task_id"]].append(t)
        per_task_rate = {
            task: sum(1 for t in ts if t["passed"]) / len(ts)
            for task, ts in sorted(by_task.items())
        }
        # Bootstrap over per-task pass rates, not over raw trials: the task is
        # the unit of replication, and k trials of one task are not k
        # independent observations of the pool.
        point, lo, hi = bootstrap_ci(list(per_task_rate.values()), statistic=_mean)

        solved = sum(1 for t in trials if t["passed"])
        tokens = sum(t["input_tokens"] + t["output_tokens"] for t in trials)
        calls = sum(t["model_calls"] for t in trials)
        recalled = sum(t.get("recalled_tokens", 0) for t in trials)
        frames = sum(t.get("recalled_frames", 0) for t in trials)
        cited = sum(t.get("cited_frames", 0) for t in trials)

        out[(arm, epoch)] = ArmEpoch(
            arm=arm,
            epoch=epoch,
            trials=len(trials),
            solved=solved,
            accuracy=point,
            accuracy_lo=lo,
            accuracy_hi=hi,
            per_task_rate=per_task_rate,
            tokens_per_solved=_safe_div(tokens, solved),
            cost_per_solved=_safe_div(sum(t["cost_usd"] for t in trials), solved),
            seconds_per_solved=_safe_div(sum(t["wall_clock_s"] for t in trials), solved),
            calls_per_solved=_safe_div(calls, solved),
            recalled_tokens_per_call=_safe_div(recalled, calls),
            cited_share=_safe_div(cited, frames),
            store_memories=max(
                (t.get("store_stats", {}) or {}).get("memories", 0) for t in trials
            ),
        )
    return out


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


@dataclass
class PairedComparison:
    epoch: int
    arm_a: str
    arm_b: str
    per_task_delta: dict[str, float]
    delta: float
    lo: float
    hi: float
    significant: bool
    meaningful: bool

    def verdict(self) -> str:
        if not self.significant:
            return "no detectable difference (CI spans zero)"
        if not self.meaningful:
            return f"statistically separated but below the pre-registered {MIN_MEANINGFUL_EFFECT:.0%} threshold"
        return "difference exceeds the pre-registered threshold"


def paired(
    summary: dict[tuple[str, int], ArmEpoch], epoch: int, arm_a: str, arm_b: str
) -> PairedComparison | None:
    """Paired per-task difference arm_a - arm_b at one epoch."""
    a = summary.get((arm_a, epoch))
    b = summary.get((arm_b, epoch))
    if not a or not b:
        return None
    tasks = sorted(set(a.per_task_rate) & set(b.per_task_rate))
    deltas = {t: a.per_task_rate[t] - b.per_task_rate[t] for t in tasks}
    point, lo, hi = bootstrap_ci(list(deltas.values()), statistic=_mean)
    significant = not (lo <= 0.0 <= hi)
    return PairedComparison(
        epoch=epoch,
        arm_a=arm_a,
        arm_b=arm_b,
        per_task_delta=deltas,
        delta=point,
        lo=lo,
        hi=hi,
        significant=significant,
        meaningful=significant and abs(point) >= MIN_MEANINGFUL_EFFECT,
    )


def regression_rate(summary: dict[tuple[str, int], ArmEpoch], arm: str) -> list[dict]:
    """Tasks solved at epoch N that fail at N+1.

    The metric usually left out, and the one that catches a system learning
    net-positive while silently breaking things it used to get right. A task
    counts as solved at an epoch when a majority of its k trials pass.
    """
    epochs = sorted(e for (a, e) in summary if a == arm)
    out = []
    for prev, nxt in zip(epochs, epochs[1:]):
        before = summary[(arm, prev)].per_task_rate
        after = summary[(arm, nxt)].per_task_rate
        solved_before = {t for t, r in before.items() if r >= 0.5}
        regressed = sorted(t for t in solved_before if after.get(t, 0.0) < 0.5)
        out.append(
            {
                "from_epoch": prev,
                "to_epoch": nxt,
                "solved_before": len(solved_before),
                "regressed": len(regressed),
                "rate": _safe_div(len(regressed), len(solved_before)),
                "tasks": regressed,
            }
        )
    return out


def control_null(summary: dict[tuple[str, int], ArmEpoch]) -> dict:
    """The empirical null: how much an arm moves for no reason at all.

    The control arm does no experience work and its store is wiped before every
    evaluation, so control at E0, E1, … E4 is *the same experiment repeated*.
    Its spread across epochs is therefore a direct measurement of this setup's
    run-to-run noise, requiring no extra runs and no distributional assumption.

    This matters more than it might sound. In the first attempt at series 001,
    control moved 18/30 → 24/30 between two epochs that were identical by
    construction — a swing of 0.20, twice the pre-registered effect threshold.
    Any treatment movement smaller than this band is indistinguishable from
    nothing, however tidy the point estimate looks.
    """
    epochs = sorted(e for (a, e) in summary if a == "control")
    values = [summary[("control", e)].accuracy for e in epochs]
    if len(values) < 2:
        return {"replications": len(values), "spread": float("nan"), "range": float("nan")}
    mean = _mean(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return {
        "replications": len(values),
        "values": values,
        "mean": mean,
        "spread": variance**0.5,
        "range": max(values) - min(values),
    }


def verdict(summary: dict[tuple[str, int], ArmEpoch]) -> dict:
    """Answer the pre-registered question, using the pre-registered rules.

    The rules were fixed before the first trial ran, so this function is not
    allowed to be clever. It reads the final epoch's paired contrasts and the
    treatment arm's trend and maps them onto the falsification conditions from
    `PREREGISTRATION.md`. "No effect" is a first-class outcome here, not a
    failure of the experiment.
    """
    epochs = sorted({e for (_, e) in summary})
    if len(epochs) < 2:
        return {"claim": "undetermined", "reason": "a single epoch proves nothing"}

    last = epochs[-1]
    t_vs_c = paired(summary, last, "treatment", "control")
    t_vs_s = paired(summary, last, "treatment", "sham")
    t_trend = trend(summary, "treatment")
    c_trend = trend(summary, "control")

    regressions = regression_rate(summary, "treatment")
    total_regressed = sum(r["regressed"] for r in regressions)
    total_solved_before = sum(r["solved_before"] for r in regressions)

    # Treatment's movement has to clear the control arm's own noise. Control is
    # the same experiment repeated, so anything it does too is not memory.
    null = control_null(summary)
    control_drift = abs(c_trend.get("delta", 0.0) or 0.0)
    treatment_delta = t_trend.get("delta", 0.0) or 0.0
    null_range = null.get("range", float("nan"))
    clears_null = (
        abs(treatment_delta) > null_range if null_range == null_range else False
    )

    supported = bool(
        t_vs_c
        and t_vs_c.meaningful
        and t_vs_c.delta > 0
        and t_vs_s
        and t_vs_s.meaningful
        and t_vs_s.delta > 0
    )

    # The pre-registration says "the series is the result; a single epoch pair
    # proves nothing". That has to bind when the numbers come out *favourable*
    # or it was never a commitment. Two epochs is one pair.
    preliminary = len(epochs) < 3

    if supported:
        claim = "supported — PRELIMINARY ONLY" if preliminary else "supported"
        reason = (
            "treatment exceeds both control and sham by more than the "
            "pre-registered threshold, with CIs excluding zero"
        )
        if preliminary:
            reason += (
                f"; but this is {len(epochs)} epochs — a single pair — and the "
                f"pre-registration commits to the series being the result. "
                f"Directional evidence, not a finding"
            )
    elif t_vs_s and t_vs_c and t_vs_c.meaningful and t_vs_c.delta > 0 and not t_vs_s.meaningful:
        claim = "not supported — volume, not content"
        reason = (
            "treatment beats control but does not separate from sham, so having "
            "context helped and having the *right* context did not"
        )
    else:
        claim = "not supported — no detectable transfer"
        reason = (
            "treatment does not separate from control by more than the "
            "pre-registered threshold at the final epoch"
        )

    return {
        "claim": claim,
        "reason": reason,
        "preliminary": preliminary,
        "final_epoch": last,
        "treatment_minus_control": None if not t_vs_c else {
            "delta": t_vs_c.delta, "ci": [t_vs_c.lo, t_vs_c.hi], "verdict": t_vs_c.verdict()
        },
        "treatment_minus_sham": None if not t_vs_s else {
            "delta": t_vs_s.delta, "ci": [t_vs_s.lo, t_vs_s.hi], "verdict": t_vs_s.verdict()
        },
        "treatment_trend": treatment_delta,
        "control_drift": control_drift,
        "treatment_clears_control_drift": abs(treatment_delta) > control_drift,
        "control_null": null,
        "treatment_clears_control_null_range": clears_null,
        "underpowered": (
            null_range > MIN_MEANINGFUL_EFFECT if null_range == null_range else None
        ),
        "regression_rate": _safe_div(total_regressed, total_solved_before),
        "regressed_task_instances": total_regressed,
    }


def trend(summary: dict[tuple[str, int], ArmEpoch], arm: str) -> dict:
    """Does accuracy move across the series, and does it clear control's noise?"""
    epochs = sorted(e for (a, e) in summary if a == arm)
    if len(epochs) < 2:
        return {"arm": arm, "epochs": epochs, "delta": float("nan")}
    first, last = summary[(arm, epochs[0])], summary[(arm, epochs[-1])]
    return {
        "arm": arm,
        "epochs": epochs,
        "first": first.accuracy,
        "last": last.accuracy,
        "delta": last.accuracy - first.accuracy,
    }
