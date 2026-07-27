"""The epoch runner.

    E0: evaluate (cold — no experience)
        → work a block of experience tasks
    E1: evaluate
        → work another block
    E2: evaluate …

The series is the result. A single epoch pair proves nothing, which is why the
runner is built around appending to one JSONL rather than around producing a
number.

Evaluation always precedes the experience block within an epoch, so epoch *N*
measures exactly the experience accumulated in epochs *< N* and never the block
that is about to be worked.

Results are append-only. Losses are committed with wins; a scoreboard that only
rises is a scoreboard nobody should believe.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .arms import ARMS, Arm, reset_store, store_stats
from .config import (
    PinnedConfig,
    assert_series_compatible,
    env_for_run,
    workspace_settings,
)
from .leakage import EpochInvalidated, gate
from .runner import STORE_DIR, Trial, run_trial
from .tasks import CORPUS, Task, default_work_root, load_pool


@dataclass
class SeriesPaths:
    """Where a series keeps its results, and where it keeps its scratch.

    They are deliberately in different places. Results belong in the repository
    and are committed; workspaces and per-arm stores live *outside* it, because
    anything under the repo root is reachable by an agent whose project root
    resolves there — which is how an early run edited the pristine corpus and
    handed itself a free pass. See `tasks.corpus_digest`.
    """

    root: Path

    @property
    def results(self) -> Path:
        return self.root / "results.jsonl"

    @property
    def epochs(self) -> Path:
        return self.root / "epochs.jsonl"

    @property
    def scratch(self) -> Path:
        return default_work_root(self.root.name)

    @property
    def work(self) -> Path:
        return self.scratch / "work"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.scratch / "stores").mkdir(parents=True, exist_ok=True)
        self.work.mkdir(parents=True, exist_ok=True)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _foreign_task_workspace(task: Task, dest: Path, corpus: Path) -> None:
    """Sham tasks run against the foreign corpus, which has no ledger setup."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(corpus, dest)


def run_experience_block(
    arm: Arm,
    tasks: list[Task],
    *,
    epoch: int,
    paths: SeriesPaths,
    config: PinnedConfig,
    log,
) -> list[Trial]:
    """Work a block of experience tasks, serially, letting the store accumulate.

    Serial on purpose: the arm has one SQLite store and the whole point is that
    trial *n+1* sees what trial *n* learned.
    """
    if not arm.accumulates or not tasks:
        return []
    store = arm.store(paths.scratch)
    store.mkdir(parents=True, exist_ok=True)
    trials: list[Trial] = []
    for i, task in enumerate(tasks):
        ws = paths.work / f"{arm.name}-exp-{epoch}-{i}-{task.task_id}"
        sandbox = paths.work / f"{arm.name}-exp-{epoch}-{i}-score"
        if arm.name == "sham":
            trial = _run_foreign(task, arm, epoch, i, ws, config, store, paths)
        else:
            trial = run_trial(
                task,
                arm=arm.name,
                epoch=epoch,
                trial_index=i,
                workspace=ws,
                sandbox=sandbox,
                config=config,
                store=store,
                learn=True,
            )
        trials.append(trial)
        log(
            f"    experience {arm.name} {task.task_id}: "
            f"{'pass' if trial.passed else 'fail'} ${trial.cost_usd:.4f}"
        )
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(sandbox, ignore_errors=True)
    return trials


def _run_foreign(task, arm, epoch, index, ws, config, store, paths) -> Trial:
    """A sham experience trial: real work, foreign domain, never scored.

    Sham trials produce store content, not measurements, so they carry no
    verifier. `passed` is left False and must never be read as a result — the
    scoreboard filters on `pool == "evaluation"` for exactly this reason.
    """
    import subprocess
    import time

    from .config import env_for_run, observed_models, workspace_settings
    from .runner import STORE_DIR, _extract_envelope, harvest_store

    _foreign_task_workspace(task, ws, arm.experience_corpus)
    (ws / ".stella").mkdir(exist_ok=True)
    (ws / ".stella" / "settings.json").write_text(
        json.dumps(workspace_settings(config), indent=2)
    )
    if store.exists():
        shutil.copytree(store, ws / STORE_DIR, dirs_exist_ok=True)

    trial = Trial(
        task_id=task.task_id, pool="sham", arm=arm.name, epoch=epoch, trial=index
    )
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [
                config.stella_binary,
                "run",
                "--output-format",
                "json",
                "--budget",
                str(config.budget_usd),
                task.prompt,
            ],
            cwd=str(ws),
            capture_output=True,
            text=True,
            env=env_for_run(config),
            timeout=900,
        )
        stdout = proc.stdout
    except subprocess.TimeoutExpired:
        trial.status = "timeout"
        stdout = ""
    trial.wall_clock_s = time.monotonic() - started
    envelope = _extract_envelope(stdout)
    if envelope:
        events = envelope.get("events") or []
        trial.status = envelope.get("status") or ""
        trial.cost_usd = float(envelope.get("cost_usd") or 0.0)
        trial.models_observed = observed_models(events)
        trial.model_calls = sum(1 for e in events if e.get("type") == "step_usage")
    harvest_store(ws, store)
    return trial


def pump_store(store: Path, config: PinnedConfig, log) -> dict:
    """Extract observations from the reflection log into the context store.

    This is an intervention, and it is recorded as one. On the `stella run`
    path nothing ever advances reflection lessons into `context_records` on its
    own — the log grows, and the lifecycle downstream of it stays empty. Left
    alone, the treatment arm would carry no durable content at all and the
    experiment would be measuring plumbing rather than transfer.

    `stella proposals refresh` is the documented, offline, zero-cost command
    that performs the extraction, so the harness calls it rather than writing
    to the store itself.
    """
    if not config.pump_proposals or not store.exists():
        return {"pumped": False}
    scratch = store.parent / f"_pump-{store.name}"
    shutil.rmtree(scratch, ignore_errors=True)
    (scratch / STORE_DIR).parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(store, scratch / STORE_DIR)
    (scratch / ".stella" / "settings.json").write_text(
        json.dumps(workspace_settings(config), indent=2)
    )
    try:
        proc = subprocess.run(
            [config.stella_binary, "proposals", "refresh"],
            cwd=str(scratch),
            capture_output=True,
            text=True,
            env=env_for_run(config),
            timeout=300,
        )
        out = (proc.stdout + proc.stderr).strip().splitlines()
        detail = out[-1] if out else ""
    except subprocess.TimeoutExpired:
        detail = "timeout"
    shutil.copytree(scratch / STORE_DIR, store, dirs_exist_ok=True)
    shutil.rmtree(scratch, ignore_errors=True)
    log(f"    pump: {detail}")
    return {"pumped": True, "detail": detail}


def run_evaluation(
    arm: Arm,
    *,
    epoch: int,
    k: int,
    paths: SeriesPaths,
    config: PinnedConfig,
    concurrency: int,
    log,
    sink=None,
) -> list[Trial]:
    """Evaluate the held-out pool.

    Every trial gets its own workspace *and its own copy* of the arm's store,
    and neither is written back. Measuring must not become experience.

    Because nothing is written back, evaluation trials are independent and can
    run concurrently — which is what makes k>=5 affordable.
    """
    tasks = load_pool("evaluation")
    store = arm.store(paths.scratch) if arm.seeded_evaluation else None
    jobs = [(task, i) for task in tasks for i in range(k)]

    def one(job) -> Trial:
        task, i = job
        ws = paths.work / f"{arm.name}-eval-{epoch}-{task.task_id}-{i}"
        sandbox = paths.work / f"{arm.name}-eval-{epoch}-{task.task_id}-{i}-score"
        try:
            return run_trial(
                task,
                arm=arm.name,
                epoch=epoch,
                trial_index=i,
                workspace=ws,
                sandbox=sandbox,
                config=config,
                store=store,
                learn=False,
            )
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(sandbox, ignore_errors=True)

    trials: list[Trial] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(one, job): job for job in jobs}
        for future in as_completed(futures):
            trial = future.result()
            trials.append(trial)
            if sink is not None:
                sink(trial)
            log(
                f"    eval {arm.name} E{epoch} {trial.task_id}#{trial.trial}: "
                f"{'PASS' if trial.passed else 'fail'} ${trial.cost_usd:.4f}"
            )
    return trials


def run_series(
    *,
    root: Path,
    epochs: int,
    k: int,
    block_size: int,
    config: PinnedConfig,
    arms: list[str] | None = None,
    concurrency: int = 4,
    log=print,
) -> None:
    """Run a full series and append every trial to `results.jsonl`."""
    paths = SeriesPaths(root)
    paths.ensure()
    assert_series_compatible(paths.results, config)

    selected = [ARMS[name] for name in (arms or list(ARMS))]
    for arm in selected:
        reset_store(arm, paths.scratch)

    experience = {arm.name: arm.experience_pool() for arm in selected}
    cursor = {arm.name: 0 for arm in selected}

    for epoch in range(epochs):
        log(f"\n=== epoch {epoch} ===")
        for arm in selected:
            store = arm.store(paths.scratch)

            # The gate runs before scoring, on the store the epoch will use.
            leak = None
            if arm.seeded_evaluation and store.exists():
                try:
                    leak = gate(store, arm.name, epoch)
                except EpochInvalidated as exc:
                    _append(
                        paths.epochs,
                        {
                            "epoch": epoch,
                            "arm": arm.name,
                            "invalidated": True,
                            "reason": str(exc)[:2000],
                            "config_fingerprint": config.fingerprint(),
                        },
                    )
                    log(f"  !! {exc}")
                    raise
            stats = store_stats(store)
            log(
                f"  {arm.name}: store {stats['memories']} memories / "
                f"{stats['episodes']} episodes / {stats['context_records']} records"
                + (f" — leak scan {leak.summary()}" if leak else "")
            )

            def sink(trial: Trial, _stats=stats) -> None:
                row = trial.as_row()
                row.update(
                    {
                        "config": config.as_dict(),
                        "config_fingerprint": config.fingerprint(),
                        "store_stats": _stats,
                    }
                )
                _append(paths.results, row)

            trials = run_evaluation(
                arm,
                epoch=epoch,
                k=k,
                paths=paths,
                config=config,
                concurrency=concurrency,
                log=log,
                sink=sink,
            )

            solved = sum(1 for t in trials if t.passed)
            _append(
                paths.epochs,
                {
                    "epoch": epoch,
                    "arm": arm.name,
                    "invalidated": False,
                    "leak_scan": leak.as_dict() if leak else None,
                    "store_stats": stats,
                    "eval_trials": len(trials),
                    "eval_solved": solved,
                    "eval_cost_usd": round(sum(t.cost_usd for t in trials), 6),
                    "config_fingerprint": config.fingerprint(),
                },
            )
            log(f"  {arm.name} E{epoch}: {solved}/{len(trials)} solved")

        # Experience block for the *next* epoch.
        #
        # Serial *within* an arm — the whole point is that trial n+1 sees what
        # trial n learned — but the arms hold separate stores and share nothing,
        # so they are worked concurrently.
        if epoch + 1 < epochs:

            def work(arm: Arm) -> list[Trial]:
                pool_tasks = experience[arm.name]
                if not pool_tasks:
                    return []
                start = cursor[arm.name]
                block = [
                    pool_tasks[(start + i) % len(pool_tasks)] for i in range(block_size)
                ]
                cursor[arm.name] = start + block_size
                log(f"  working {block_size} experience tasks for {arm.name}")
                trials = run_experience_block(
                    arm, block, epoch=epoch, paths=paths, config=config, log=log
                )
                pump_store(arm.store(paths.scratch), config, log)
                return trials

            with ThreadPoolExecutor(max_workers=max(1, len(selected))) as pool:
                blocks = list(pool.map(work, selected))

            for arm, exp_trials in zip(selected, blocks):
                stats = store_stats(arm.store(paths.scratch))
                for trial in exp_trials:
                    row = trial.as_row()
                    row.update(
                        {
                            "config": config.as_dict(),
                            "config_fingerprint": config.fingerprint(),
                            "store_stats": stats,
                        }
                    )
                    _append(paths.results, row)
