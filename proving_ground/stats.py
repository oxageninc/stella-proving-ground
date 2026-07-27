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

**Correctness is not the only outcome** (finding 12). Scoring one bit per trial
concluded "context did not help" while the same 192 trials showed the context
arm using a quarter fewer model calls, a third less money, and never once
needing to be steered. Pass rate *saturates* on this pool — control scores 0.95
on checks and five of twelve tasks are perfect in every arm — while effort does
not: an agent that always succeeds can still take 19 turns or 93. So the
continuous outcomes are computed here as first-class results beside accuracy,
not dug out of failure diagnostics afterwards.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Callable

BOOTSTRAP_SEED = 20260726
BOOTSTRAP_DRAWS = 10000

#: Pre-registered: the smallest treatment-minus-control difference in
#: resolution accuracy that counts as a result. Below this, we report no effect
#: regardless of what the point estimate does.
MIN_MEANINGFUL_EFFECT = 0.10


@dataclass(frozen=True)
class Outcome:
    """One scored axis.

    `completed_only` is the load-bearing field. An abort truncates a run, so a
    trial that gave up at step 12 records less effort than one that worked
    honestly to step 60 — including aborts in an effort contrast therefore
    *rewards* whichever arm quits more. The arms differ a lot on abort rate
    (series 001: 33% of trials aborted, against 15% in the probe), which is a
    result in its own right and is reported separately rather than smuggled
    into the effort numbers.

    Steering is the exception and is scored over **all** trials: "the agent was
    warned and looped anyway" is only observable on runs that went wrong, so
    restricting it to completed trials would define the outcome out of
    existence.
    """

    key: str
    label: str
    extract: Callable[[dict], float]
    completed_only: bool
    fmt: str = ".3f"
    #: Direction help points in. Every continuous outcome here is a cost.
    lower_is_better: bool = True


def _stuck_loop(row: dict) -> float:
    """The harness's own 'warned, then looped anyway' signal.

    The closest proxy this design has for "a human had to intervene": these are
    one-shot headless trials, so nobody is there to intervene, but Stella emits
    a steering warning and the trial records whether the agent carried on
    looping regardless.
    """
    return float("stuck-loop" in (row.get("stella_error") or ""))


#: Effort per **trial** — deliberately not the `*_per_solved` fields, which
#: divide by the number of passes and so conflate effort with correctness. When
#: pass rate is saturated the denominator is nearly constant and the two agree;
#: when it is not, `cost_per_solved` moves because accuracy moved, and reads as
#: an efficiency change that never happened.
EFFORT_OUTCOMES: tuple[Outcome, ...] = (
    Outcome("model_calls", "model calls", lambda r: float(r.get("model_calls") or 0), True, ".1f"),
    Outcome("cost_usd", "cost (USD)", lambda r: float(r.get("cost_usd") or 0.0), True, ".4f"),
    Outcome("output_tokens", "output tokens", lambda r: float(r.get("output_tokens") or 0), True, ".0f"),
)

STEERING_OUTCOME = Outcome("stuck_loop", "stuck-loop rate", _stuck_loop, False, ".3f")

#: Everything scored beside accuracy.
CONTINUOUS_OUTCOMES: tuple[Outcome, ...] = EFFORT_OUTCOMES + (STEERING_OUTCOME,)

OUTCOMES_BY_KEY: dict[str, Outcome] = {o.key: o for o in CONTINUOUS_OUTCOMES}


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
    #: outcome key -> {task_id: mean over that task's eligible trials}. The unit
    #: the bootstrap resamples, for every continuous outcome.
    per_task_outcome: dict[str, dict[str, float]] = field(default_factory=dict)
    #: outcome key -> mean over eligible trials, pooled. Reported, never
    #: resampled: the task is the unit of replication.
    outcome_mean: dict[str, float] = field(default_factory=dict)
    #: How many trials survived the `completed` filter, so a reader can see when
    #: an effort number rests on very little.
    completed: int = 0
    aborted: int = 0


def _safe_div(a: float, b: float) -> float:
    return a / b if b else float("nan")


def _eligible(trials: list[dict], outcome: Outcome) -> list[dict]:
    if not outcome.completed_only:
        return trials
    return [t for t in trials if t.get("status") == "completed"]


def per_task_outcome(trials: list[dict], outcome: Outcome) -> dict[str, float]:
    """Mean of `outcome` per task over the trials it is eligible to score.

    A task with no eligible trials is **absent** rather than NaN, so a paired
    contrast drops it from both arms instead of poisoning the mean.
    """
    acc: dict[str, list[float]] = defaultdict(list)
    for t in _eligible(trials, outcome):
        acc[t["task_id"]].append(outcome.extract(t))
    return {task: _mean(vals) for task, vals in sorted(acc.items()) if vals}


def summarize(rows: list[dict], *, require_full_coverage: bool = True) -> dict[tuple[str, int], ArmEpoch]:
    """Per arm, per epoch: the pre-registered metric table.

    Arm-epochs that do not cover the whole evaluation pool are **dropped, not
    scored**. A series stopped mid-cell — by a budget guard, a crash, or a
    human — leaves a partial arm-epoch behind, and averaging it produces a
    number that looks like the others and is not comparable to them.

    This is not hypothetical: stopping a run during `sham E1` left that cell
    holding one trial of one task, which scored as a complete arm-epoch and
    yielded `treatment - sham = -0.800` with a **zero-width** confidence
    interval, because a bootstrap over a single task resamples the same value
    every draw. A degenerate CI is the tell, and nothing in the pipeline was
    looking for it.
    """
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in evaluation_rows(rows):
        grouped[(row["arm"], row["epoch"])].append(row)

    if require_full_coverage:
        expected = {row["task_id"] for row in evaluation_rows(rows)}
        grouped = {
            key: trials
            for key, trials in grouped.items()
            if {t["task_id"] for t in trials} == expected
        }

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
            per_task_outcome={
                o.key: per_task_outcome(trials, o) for o in CONTINUOUS_OUTCOMES
            },
            outcome_mean={
                o.key: _mean([o.extract(t) for t in _eligible(trials, o)])
                for o in CONTINUOUS_OUTCOMES
            },
            completed=sum(1 for t in trials if t.get("status") == "completed"),
            aborted=sum(1 for t in trials if t.get("status") not in ("completed", "")),
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
    #: Which axis this contrast is on. "accuracy" is the pre-registered primary.
    outcome: str = "accuracy"
    #: arm_b's mean over the same shared tasks, so a delta can be read as a
    #: percentage of the baseline it is a change from.
    baseline: float = float("nan")
    n_tasks: int = 0

    @property
    def relative(self) -> float:
        """Delta as a share of the baseline arm, or NaN when the baseline is 0."""
        if self.baseline != self.baseline or not self.baseline:
            return float("nan")
        return self.delta / self.baseline

    def verdict(self) -> str:
        if self.outcome != "accuracy":
            # No threshold was pre-registered for the continuous outcomes, and
            # inventing one after seeing the probe's numbers would be exactly
            # the move this repo exists to avoid. Report separation and size.
            if not self.significant:
                return "within noise (CI spans zero)"
            return "CI excludes zero"
        if not self.significant:
            return "no detectable difference (CI spans zero)"
        if not self.meaningful:
            return f"statistically separated but below the pre-registered {MIN_MEANINGFUL_EFFECT:.0%} threshold"
        return "difference exceeds the pre-registered threshold"


def _paired_from_maps(
    a_map: dict[str, float],
    b_map: dict[str, float],
    *,
    epoch: int,
    arm_a: str,
    arm_b: str,
    outcome: str,
) -> PairedComparison | None:
    """Bootstrap the paired per-task delta between two per-task maps.

    Pairing happens on the **intersection**: a task the completed-trial filter
    emptied in one arm is dropped from both, never treated as zero.
    """
    tasks = sorted(set(a_map) & set(b_map))
    if not tasks:
        return None
    deltas = {t: a_map[t] - b_map[t] for t in tasks}
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
        meaningful=(
            significant and abs(point) >= MIN_MEANINGFUL_EFFECT
            if outcome == "accuracy"
            else significant
        ),
        outcome=outcome,
        baseline=_mean([b_map[t] for t in tasks]),
        n_tasks=len(tasks),
    )


def paired(
    summary: dict[tuple[str, int], ArmEpoch], epoch: int, arm_a: str, arm_b: str
) -> PairedComparison | None:
    """Paired per-task accuracy difference arm_a - arm_b at one epoch."""
    a = summary.get((arm_a, epoch))
    b = summary.get((arm_b, epoch))
    if not a or not b:
        return None
    return _paired_from_maps(
        a.per_task_rate, b.per_task_rate,
        epoch=epoch, arm_a=arm_a, arm_b=arm_b, outcome="accuracy",
    )


def paired_outcome(
    summary: dict[tuple[str, int], ArmEpoch],
    epoch: int,
    arm_a: str,
    arm_b: str,
    key: str,
) -> PairedComparison | None:
    """Paired per-task difference on one continuous outcome, same machinery.

    Negative is *better* for every key in `CONTINUOUS_OUTCOMES`: they are all
    costs — calls, dollars, tokens, and how often the agent had to be steered.
    """
    a = summary.get((arm_a, epoch))
    b = summary.get((arm_b, epoch))
    if not a or not b:
        return None
    return _paired_from_maps(
        a.per_task_outcome.get(key, {}), b.per_task_outcome.get(key, {}),
        epoch=epoch, arm_a=arm_a, arm_b=arm_b, outcome=key,
    )


#: Every arm pair the scoreboard contrasts, in the order the questions matter.
CONTRAST_PAIRS: tuple[tuple[str, str], ...] = (
    ("treatment", "control"),
    ("treatment", "sham"),
    ("sham", "control"),
)


def family_wise_error(n_contrasts: int, alpha: float = 0.05) -> float:
    """P(at least one of `n_contrasts` independent CIs excludes 0 by chance).

    Reported rather than corrected. A Bonferroni correction applied after the
    fact to a family whose size grew as the analysis grew is not a correction,
    it is a negotiation; stating the number lets a reader discount accordingly.
    """
    if n_contrasts <= 0:
        return 0.0
    return 1.0 - (1.0 - alpha) ** n_contrasts


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


def continuous_verdict(summary: dict[tuple[str, int], ArmEpoch], epoch: int) -> dict:
    """The effort and steering contrasts at one epoch, for both key arm pairs.

    Separate from `verdict()`'s pre-registered accuracy machinery on purpose.
    These outcomes were added *after* seeing finding 12's probe, so they are
    exploratory and are labelled as such — they cannot be dressed up as having
    been pre-registered, and a threshold chosen now would be chosen knowing the
    answer.
    """
    out: dict = {"epoch": epoch, "contrasts": {}, "n_contrasts": 0}
    for arm_a, arm_b in (("treatment", "control"), ("treatment", "sham")):
        for o in CONTINUOUS_OUTCOMES:
            c = paired_outcome(summary, epoch, arm_a, arm_b, o.key)
            if c is None:
                continue
            out["contrasts"][f"{arm_a}-{arm_b}/{o.key}"] = {
                "delta": c.delta,
                "ci": [c.lo, c.hi],
                "relative": c.relative,
                "baseline": c.baseline,
                "significant": c.significant,
                "n_tasks": c.n_tasks,
            }
            out["n_contrasts"] += 1

    # The headline the probe predicted: treatment spends less to get there.
    helped = [
        k for k, v in out["contrasts"].items()
        if k.startswith("treatment-control/") and v["significant"] and v["delta"] < 0
    ]
    hurt = [
        k for k, v in out["contrasts"].items()
        if k.startswith("treatment-control/") and v["significant"] and v["delta"] > 0
    ]
    if helped and not hurt:
        out["claim"] = "treatment is cheaper than control on " + ", ".join(
            k.split("/")[1] for k in helped
        )
    elif hurt and not helped:
        out["claim"] = "treatment is more expensive than control on " + ", ".join(
            k.split("/")[1] for k in hurt
        )
    elif helped and hurt:
        out["claim"] = "mixed — treatment is cheaper on some axes and dearer on others"
    else:
        out["claim"] = "no detectable effort or steering difference (every CI spans zero)"
    return out


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
        # Secondary, exploratory, and the axis finding 12 says carries the
        # signal on a pool this saturated. Reported beside the primary claim so
        # a reader cannot take the accuracy verdict as the whole answer.
        "continuous": continuous_verdict(summary, last),
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
