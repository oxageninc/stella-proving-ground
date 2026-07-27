"""Does recall *precision* matter, or is presence of the fact enough?

Three series showed no transfer from accumulated context. That leaves two very
different explanations, and the roadmap is opposite depending on which holds:

* **acquisition** — the lifecycle mines the wrong things (measured: 8 of 10
  stored memories were agent self-critique, 0 captured a convention that
  decided pass/fail), or
* **retrieval / injection / irrelevance** — the facts would not help even if
  they arrived perfectly.

This probe settles it by bypassing the lifecycle entirely — no store, no
recall, no ranking — and hand-delivering context in the prompt. It is not a
measurement of Stella's memory; it measures the ceiling memory is aiming at.

Three arms, identical in every respect except the block appended to the prompt:

    control   nothing appended. What the agent does unaided.
    oracle    the four house conventions the verifiers enforce, and nothing else.
    diluted   the same four facts, interleaved with eight process memories
              taken verbatim from a live treatment store (series-002) — the
              actual output of the mining loop.

Holding fact CONTENT constant at oracle quality and varying only what surrounds
it isolates precision from acquisition:

    oracle ~= control   the facts do not help even when delivered perfectly.
                        Fixing acquisition or retrieval is pointless; the
                        premise is wrong.
    oracle >> control   the facts DO help. Everything between mining and
                        injection is worth fixing.
    oracle ~= diluted   noise is harmless; presence is enough, and a
                        deterministic graph index buys little.
    diluted ~= control  noise DROWNS the signal. Precision is the bottleneck
                        and anchoring recall to files/symbols is the fix.

Why this supersedes `oracle_probe.py`: that script baselined against pooled
cold control from series-001/-002, which ran on task-pool digest c6cbc594. The
pool has since been rebuilt (12 tasks, ~5 named checks each, seeded before
asserting) and is now f8a7dfe7. A cross-digest comparison measures the
instrument change, not the treatment. Here the control arm is run fresh,
interleaved with the other two, so all three share a digest by construction.

Scored at the level of named checks rather than one bit per task. The bootstrap
resamples TASKS, so n=12 is what decides the width of the interval; k buys
precision within a task and is deliberately small.

KNOWN LIMITATION: there is no noise-only arm (eight process memories, no
facts). With one, this would be a clean 2x2 separating "more context changes
behaviour" from "these particular facts help". Without it, a diluted result
that lands between control and oracle has two readings. It was cut for budget,
not because it is uninteresting.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proving_ground.config import PinnedConfig  # noqa: E402
from proving_ground.runner import run_trial  # noqa: E402
from proving_ground.tasks import default_work_root, load_pool  # noqa: E402

#: The four conventions `CONTRIBUTING.md` documents and the verifiers enforce,
#: written as flat statements of fact about the code — the shape a domain
#: lesson is supposed to take, and the shape none of the mined ones did.
#: Rendered like a recall block so the model meets them in the familiar form.
FACTS = [
    "house convention — Every command handler must be registered in the COMMANDS dict in ledgerctl/registry.py. main.py dispatches only through that registry, so an unregistered handler is unreachable and reports \"unknown command\".",
    "house convention — Money is handled as integer minor units (cents) everywhere. Parse user input with money.parse_amount(\"12.50\") -> 1250 and render with money.format_amount(1250) -> \"12.50\". Floats are never used for ledger amounts, and every amount stored in the ledger file is an int.",
    "house convention — Expected failures raise a subclass of LedgerError from ledgerctl/errors.py (UnknownAccount, InsufficientFunds, ValidationError). main.py catches LedgerError and nothing else, so any other exception escapes as a traceback and is a bug.",
    "house convention — Handlers do not index args directly. They call validate.require(args, \"field\", ...) first, which raises ValidationError naming the missing field.",
]

#: Verbatim from a live treatment store (series-002) — the real output of the
#: mining loop, which measured 8-in-10 process self-critique.
NOISE = [
    "When a user requests a change to a specific file, but the functionality already exists and is registered elsewhere, the agent should first verify the existing implementation and its registration point before attempting to modify the request",
    "The agent should clearly communicate where the relevant code is located and why it's not in the file the user specified.",
    "After confirming the functionality exists and is correctly registered, the agent should provide a clear summary of the status.",
    "When summarizing changes, explicitly list the files that were created or modified, including their status (e.g., new file, modified file).",
    "After making code changes, it's good practice to verify the implementation and syntax before generating a summary.",
    "The agent repeatedly called bash without any arguments or commands. This indicates a failure to understand the user's intent or a lack of a clear plan.",
    "When encountering a loop, the agent should not simply retry the same command or a slightly modified version. Instead it should pivot to a fundamentally different strategy.",
    "The agent should be more proactive in diagnosing the cause of a persistent error or loop.",
]

ARMS = ("control", "oracle", "diluted")


def _fact_line(i: int, body: str) -> str:
    return f"- [nod_oracle{i:018d}] {body}"


def _noise_line(i: int, body: str) -> str:
    return f"- [nod_noise{i:018d}] turn note — {body}"


def context_block(arm: str) -> str:
    """The only thing that differs between arms."""
    if arm == "control":
        return ""
    if arm == "oracle":
        lines = [_fact_line(i + 1, f) for i, f in enumerate(FACTS)]
        return "\nRelevant context:\n" + "\n".join(lines) + "\n"
    if arm == "diluted":
        # Interleaved, not appended: burying the facts at the end would test
        # recency rather than precision. Noise leads so the block does not open
        # with a fact.
        facts = [_fact_line(i + 1, f) for i, f in enumerate(FACTS)]
        noise = [_noise_line(i, t) for i, t in enumerate(NOISE)]
        merged: list[str] = []
        for i in range(max(len(facts), len(noise))):
            if i < len(noise):
                merged.append(noise[i])
            if i < len(facts):
                merged.append(facts[i])
        return "\nRelevant context:\n" + "\n".join(merged) + "\n"
    raise ValueError(f"unknown arm {arm!r}")


class ArmedTask:
    """A task whose prompt carries this arm's context block.

    Wraps rather than subclasses `Task` (a frozen dataclass) and forwards
    everything else, so scoring is byte-identical to a normal trial — the
    verifier cannot tell the difference, which is the point.
    """

    def __init__(self, task, arm: str):
        self._task = task
        self._arm = arm

    def __getattr__(self, name):
        return getattr(self._task, name)

    @property
    def prompt(self) -> str:
        return f"{self._task.prompt}\n{context_block(self._arm)}".rstrip() + "\n"


def credit_remaining() -> float | None:
    """Live OpenRouter credit, or None if it cannot be read."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    try:
        out = subprocess.run(
            ["curl", "-s", "-H", f"Authorization: Bearer {key}",
             "https://openrouter.ai/api/v1/credits"],
            capture_output=True, text=True, timeout=20,
        ).stdout
        d = json.loads(out)["data"]
        return float(d["total_credits"]) - float(d["total_usage"])
    except Exception:  # noqa: BLE001 — a probe must not die on a status check
        return None


def summarize(rows: list[dict]) -> None:
    """Report per-arm, then the paired per-task contrasts that carry the verdict."""
    by_arm_task_pass: dict[str, dict[str, list[bool]]] = {
        a: defaultdict(list) for a in ARMS
    }
    by_arm_checks: dict[str, list[float]] = {a: [] for a in ARMS}
    destroyed: dict[str, int] = {a: 0 for a in ARMS}

    for r in rows:
        arm = r["arm"]
        by_arm_task_pass[arm][r["task_id"]].append(bool(r["passed"]))
        checks = r.get("checks") or {}
        if checks:
            by_arm_checks[arm].append(sum(checks.values()) / len(checks))
        if r.get("destroyed_workspace"):
            destroyed[arm] += 1

    print("\n=== per arm ===")
    print(f"  {'arm':10s} {'task pass':>10s} {'check rate':>11s} {'destroyed':>10s}  n")
    for arm in ARMS:
        flat = [p for v in by_arm_task_pass[arm].values() for p in v]
        if not flat:
            continue
        task_rate = sum(flat) / len(flat)
        chk = by_arm_checks[arm]
        chk_rate = statistics.mean(chk) if chk else float("nan")
        print(f"  {arm:10s} {task_rate:>10.2f} {chk_rate:>11.2f} "
              f"{destroyed[arm]:>10d}  {len(flat)}")

    # Paired by task: the bootstrap resamples tasks, so the per-task delta is
    # the unit that matters. A mean over trials pooled across tasks would let
    # one easy task with many trials dominate.
    def per_task_rate(arm: str) -> dict[str, float]:
        return {t: sum(v) / len(v) for t, v in by_arm_task_pass[arm].items() if v}

    rates = {a: per_task_rate(a) for a in ARMS}
    for lo, hi in (("control", "oracle"), ("control", "diluted"), ("oracle", "diluted")):
        shared = sorted(set(rates[lo]) & set(rates[hi]))
        if not shared:
            continue
        deltas = [rates[hi][t] - rates[lo][t] for t in shared]
        mean = statistics.mean(deltas)
        print(f"\n=== {hi} - {lo}  (paired over {len(shared)} tasks) ===")
        for t in shared:
            print(f"  {t:22s} {lo[:7]:>7s} {rates[lo][t]:.2f}   "
                  f"{hi[:7]:>7s} {rates[hi][t]:.2f}   {rates[hi][t] - rates[lo][t]:+.2f}")
        print(f"  mean paired delta: {mean:+.3f}")

    print(f"\n  total cost: ${sum(r['cost_usd'] for r in rows):.2f}")


def main(trials: int = 4, concurrency: int = 10, floor: float = 1.50) -> int:
    config = PinnedConfig.resolve()
    root = Path("results/precision-probe")
    root.mkdir(parents=True, exist_ok=True)
    out = root / "results.jsonl"
    scratch = default_work_root("precision-probe")
    scratch.mkdir(parents=True, exist_ok=True)

    tasks = load_pool("evaluation")
    only = os.environ.get("PROBE_TASKS")
    if only:
        keep = set(only.split(","))
        tasks = [t for t in tasks if t.task_id in keep]

    jobs = [(t, arm, i) for t in tasks for arm in ARMS for i in range(trials)]
    # Interleave arms so provider-side drift over the run cannot align with an
    # arm. Seeded so the order is reproducible from the log.
    random.Random(20260727).shuffle(jobs)

    print(f"==> precision probe: {len(tasks)} tasks x {len(ARMS)} arms x k={trials} "
          f"= {len(jobs)} trials")
    print(f"    pool digest {config.task_pool_digest}  binary {config.stella_version}")
    rem = credit_remaining()
    if rem is not None:
        print(f"    credit ${rem:.2f}, stopping below ${floor:.2f}")

    stop = {"hit": False}

    def one(job):
        task, arm, i = job
        if stop["hit"]:
            return None
        ws = scratch / f"{arm}-{task.task_id}-{i}"
        sb = scratch / f"{arm}-{task.task_id}-{i}-score"
        try:
            return run_trial(
                ArmedTask(task, arm),
                arm=arm,
                epoch=0,
                trial_index=i,
                workspace=ws,
                sandbox=sb,
                config=config,
                store=None,   # no store: context arrives in the prompt or not at all
                learn=False,
            )
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(sb, ignore_errors=True)

    rows: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for trial in pool.map(one, jobs):
            if trial is None:
                continue
            row = trial.as_row()
            row.update({"config": config.as_dict(),
                        "config_fingerprint": config.fingerprint()})
            rows.append(row)
            with out.open("a") as fh:
                fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            done += 1
            chk = row.get("checks") or {}
            got = f"{sum(chk.values())}/{len(chk)}" if chk else "-"
            print(f"  [{done:3d}/{len(jobs)}] {trial.arm:8s} {trial.task_id:22s} "
                  f"{'PASS' if trial.passed else 'fail'} {got:>5s} "
                  f"${trial.cost_usd:.4f}", flush=True)
            # Stop before the account empties rather than after: running out of
            # credit mid-run turns provider errors into task failures, which
            # reads as the agent collapsing.
            if done % 12 == 0:
                rem = credit_remaining()
                if rem is not None and rem < floor:
                    print(f"\n==> BUDGET FLOOR (${rem:.2f} left) — stopping early. "
                          f"{done}/{len(jobs)} trials completed.")
                    stop["hit"] = True

    summarize(rows)
    if stop["hit"]:
        print("\n  INCOMPLETE: stopped on the budget floor. Arms are interleaved,")
        print("  so the partial run is still balanced, but k is lower than planned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
