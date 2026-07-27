"""The ceiling probe: what if the agent already knew the conventions?

Three series have shown no transfer from accumulated context. That leaves two
very different explanations, and the roadmap is opposite depending on which
holds:

* **acquisition** — the lifecycle mines the wrong things (measured: 8 of 10
  stored memories were agent self-critique, 0 captured a convention that
  decided pass/fail), or
* **retrieval / injection / irrelevance** — the facts would not help even if
  they arrived perfectly.

This probe settles it for about a dollar. It hands the agent a hand-written,
perfect context block containing exactly the four house conventions the
verifiers enforce, appended to the prompt. That deliberately **bypasses the
lifecycle entirely** — no store, no recall, no ranking. It is not a measurement
of Stella's memory; it is a measurement of the ceiling that memory is aiming at.

Read it this way:

* Oracle ≈ control  → the facts do not help even when delivered perfectly.
  Fixing acquisition or retrieval is pointless; the premise is wrong.
* Oracle >> control → the facts DO help. Everything between mining and
  injection is worth fixing, and the null result is a plumbing verdict rather
  than a verdict about context.

The comparison baseline is the pooled cold control from series-001 and -002
(10 trials per task), which reproduced to within two trials across independent
runs — a tighter baseline than a fresh control arm would be, and free.
"""

from __future__ import annotations

import json
import shutil
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
ORACLE = """
Relevant context:
- [nod_oracle000000000000000001] house convention — Every command handler must be registered in the COMMANDS dict in ledgerctl/registry.py. main.py dispatches only through that registry, so an unregistered handler is unreachable and reports "unknown command".
- [nod_oracle000000000000000002] house convention — Money is handled as integer minor units (cents) everywhere. Parse user input with money.parse_amount("12.50") -> 1250 and render with money.format_amount(1250) -> "12.50". Floats are never used for ledger amounts, and every amount stored in the ledger file is an int.
- [nod_oracle000000000000000003] house convention — Expected failures raise a subclass of LedgerError from ledgerctl/errors.py (UnknownAccount, InsufficientFunds, ValidationError). main.py catches LedgerError and nothing else, so any other exception escapes as a traceback and is a bug.
- [nod_oracle000000000000000004] house convention — Handlers do not index args directly. They call validate.require(args, "field", ...) first, which raises ValidationError naming the missing field.
"""



# --- the dilution arm ------------------------------------------------------
#
# Same four facts, buried in real noise. The memories below are verbatim from
# a live treatment store (series-002) — the actual output of the mining loop,
# which measured 8-in-10 process self-critique. Holding CONTENT constant at
# oracle quality and varying only what surrounds it isolates one question:
#
#   does recall PRECISION matter, or is it enough that the fact is present?
#
# oracle ~= diluted  -> noise is harmless; the problem is purely acquisition,
#                       and a deterministic graph index buys little.
# diluted ~= control -> noise DROWNS the signal; precision is the bottleneck,
#                       and anchoring recall to files/symbols is the fix.
REAL_MINED_NOISE = [
    "When a user requests a change to a specific file, but the functionality already exists and is registered elsewhere, the agent should first verify the existing implementation and its registration point before attempting to modify the request",
    "The agent should clearly communicate where the relevant code is located and why it's not in the file the user specified.",
    "After confirming the functionality exists and is correctly registered, the agent should provide a clear summary of the status.",
    "When summarizing changes, explicitly list the files that were created or modified, including their status (e.g., new file, modified file).",
    "After making code changes, it's good practice to verify the implementation and syntax before generating a summary.",
    "The agent repeatedly called bash without any arguments or commands. This indicates a failure to understand the user's intent or a lack of a clear plan.",
    "When encountering a loop, the agent should not simply retry the same command or a slightly modified version. Instead it should pivot to a fundamentally different strategy.",
    "The agent should be more proactive in diagnosing the cause of a persistent error or loop.",
]


def diluted_block() -> str:
    """The four facts, interleaved with eight real mined process memories.

    Interleaved rather than appended: burying them at the end would test
    recency, not precision.
    """
    facts = [ln for ln in ORACLE.strip().splitlines() if ln.startswith("- [")]
    noise = [
        f"- [nod_noise{i:018d}] turn note — {t}"
        for i, t in enumerate(REAL_MINED_NOISE)
    ]
    merged = []
    for i in range(max(len(facts), len(noise))):
        if i < len(noise):
            merged.append(noise[i])
        if i < len(facts):
            merged.append(facts[i])
        if i < len(noise) and i + 4 < len(noise):
            pass
    return "\nRelevant context:\n" + "\n".join(merged) + "\n"


def oracle_prompt(base: str) -> str:
    import os
    if os.environ.get("PROBE_MODE") == "diluted":
        return f"{base}\n{diluted_block()}"
    return f"{base}\n{ORACLE}"


class OracleTask:
    """A task whose prompt carries the perfect context block.

    Wraps rather than subclasses `Task` (frozen dataclass) and forwards
    everything else, so scoring is byte-identical to a normal trial — the
    verifier cannot tell the difference, which is the point.
    """

    def __init__(self, task):
        self._task = task

    def __getattr__(self, name):
        return getattr(self._task, name)

    @property
    def prompt(self) -> str:
        return oracle_prompt(self._task.prompt)


def pooled_control_rates() -> dict[str, float]:
    """Cold-control pass rate per task, pooled over both published series."""
    hits: dict[str, list[bool]] = defaultdict(list)
    for series in ("series-001", "series-002"):
        path = Path("results") / series / "results.jsonl"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if (
                row.get("pool") == "evaluation"
                and row.get("arm") == "control"
                and row.get("epoch") == 0
            ):
                hits[row["task_id"]].append(bool(row["passed"]))
    return {t: sum(v) / len(v) for t, v in sorted(hits.items()) if v}


def main(trials: int = 5, concurrency: int = 10) -> int:
    config = PinnedConfig.resolve()
    import os
    mode = os.environ.get("PROBE_MODE", "oracle")
    root = Path(f"results/{mode}-probe")
    root.mkdir(parents=True, exist_ok=True)
    scratch = default_work_root("oracle-probe")
    scratch.mkdir(parents=True, exist_ok=True)

    tasks = load_pool("evaluation")
    # Compare like with like: the oracle arm ran before the pool was expanded
    # from 6 tasks to 12, so a diluted run over all 12 would not be comparable.
    only = os.environ.get("PROBE_TASKS")
    if only:
        keep = set(only.split(","))
        tasks = [t for t in tasks if t.task_id in keep]
    jobs = [(t, i) for t in tasks for i in range(trials)]

    def one(job):
        task, i = job
        ws = scratch / f"oracle-{task.task_id}-{i}"
        sb = scratch / f"oracle-{task.task_id}-{i}-score"
        try:
            return run_trial(
                OracleTask(task),
                arm=os.environ.get("PROBE_MODE", "oracle"),
                epoch=0,
                trial_index=i,
                workspace=ws,
                sandbox=sb,
                config=config,
                store=None,          # no store: the facts arrive in the prompt
                learn=False,
            )
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(sb, ignore_errors=True)

    results = []
    out = root / "results.jsonl"
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for trial in pool.map(one, jobs):
            results.append(trial)
            row = trial.as_row()
            row.update(
                {"config": config.as_dict(), "config_fingerprint": config.fingerprint()}
            )
            with out.open("a") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            print(
                f"  {trial.task_id}#{trial.trial}: "
                f"{'PASS' if trial.passed else 'fail'} ${trial.cost_usd:.4f}",
                flush=True,
            )

    by_task: dict[str, list[bool]] = defaultdict(list)
    for t in results:
        by_task[t.task_id].append(t.passed)
    oracle = {t: sum(v) / len(v) for t, v in sorted(by_task.items())}
    control = pooled_control_rates()

    print(f"\n=== {mode} vs pooled cold control ===")
    deltas = []
    for task in sorted(oracle):
        o, c = oracle[task], control.get(task, float("nan"))
        deltas.append(o - c)
        print(f"  {task:20s} oracle {o:.2f}   control {c:.2f}   {o - c:+.2f}")
    mean = sum(deltas) / len(deltas)
    print(f"\n  mean paired delta: {mean:+.3f}")
    print(f"  total cost: ${sum(t.cost_usd for t in results):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
