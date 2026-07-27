"""One trial: run Stella against one task in a disposable workspace, then score.

The harness contributes no task-running or verification logic of its own beyond
this — it shells out to the Stella binary exactly as any other caller would,
and scores with a verifier the agent never sees.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import PinnedConfig, env_for_run, observed_models, workspace_settings
from .tasks import Task, materialize, score

STORE_DIR = Path(".stella") / "private"


@dataclass
class Trial:
    task_id: str
    pool: str
    arm: str
    epoch: int
    trial: int
    passed: bool = False
    detail: str = ""
    cost_usd: float = 0.0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    wall_clock_s: float = 0.0
    recalled_tokens: int = 0
    recalled_frames: int = 0
    recall_methods: list[str] = field(default_factory=list)
    cited_frames: int = 0
    models_observed: list[str] = field(default_factory=list)
    status: str = ""
    stella_error: str = ""

    def as_row(self) -> dict:
        return dict(self.__dict__)


def _extract_envelope(stdout: str) -> dict | None:
    """Pull the JSON summary out of stdout, which is prefixed with progress noise."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(stdout):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(stdout[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "schema_version" in obj:
            return obj
    return None


def prepare_workspace(task: Task, workspace: Path, config: PinnedConfig, store: Path | None) -> None:
    """Materialize the task, pin the model, and seed the arm's context store.

    `store` is the arm's `.stella/private` directory, or None for a cold run.
    It is *copied in*, never linked: an evaluation trial must be able to write
    to its store freely and have those writes discarded with the workspace.
    """
    materialize(task, workspace)
    settings_dir = workspace / ".stella"
    settings_dir.mkdir(exist_ok=True)
    (settings_dir / "settings.json").write_text(
        json.dumps(workspace_settings(config), indent=2)
    )
    if store is not None and store.exists():
        shutil.copytree(store, workspace / STORE_DIR, dirs_exist_ok=True)


def harvest_store(workspace: Path, store: Path) -> None:
    """Persist the workspace's context store back onto the arm.

    Called only for experience trials. Evaluation trials never call this —
    that omission is what keeps measurement from becoming experience.
    """
    src = workspace / STORE_DIR
    if not src.exists():
        return
    store.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, store, dirs_exist_ok=True)


def run_trial(
    task: Task,
    *,
    arm: str,
    epoch: int,
    trial_index: int,
    workspace: Path,
    sandbox: Path,
    config: PinnedConfig,
    store: Path | None,
    learn: bool,
    timeout_s: int = 900,
) -> Trial:
    """Run one task once and score it.

    `learn=True` writes the resulting store back to the arm (experience).
    `learn=False` discards it (evaluation).
    """
    result = Trial(
        task_id=task.task_id, pool=task.pool, arm=arm, epoch=epoch, trial=trial_index
    )
    prepare_workspace(task, workspace, config, store)

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
            cwd=str(workspace),
            capture_output=True,
            text=True,
            env=env_for_run(config),
            timeout=timeout_s,
        )
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        result.wall_clock_s = time.monotonic() - started
        result.status = "timeout"
        result.stella_error = f"exceeded {timeout_s}s"
        result.passed, result.detail = score(task, workspace, sandbox)
        return result
    result.wall_clock_s = time.monotonic() - started

    envelope = _extract_envelope(stdout)
    if envelope is None:
        result.status = "no-envelope"
        result.stella_error = (stderr or stdout)[-300:]
    else:
        events = envelope.get("events") or []
        result.status = envelope.get("status") or ""
        result.cost_usd = float(envelope.get("cost_usd") or 0.0)
        result.stella_error = (envelope.get("reason") or "")[:300]
        result.models_observed = observed_models(events)
        for event in events:
            kind = event.get("type")
            if kind == "step_usage":
                result.model_calls += 1
                result.input_tokens += int(event.get("input_tokens") or 0)
                result.output_tokens += int(event.get("output_tokens") or 0)
                result.cached_input_tokens += int(event.get("cached_input_tokens") or 0)
            elif kind == "context_recall":
                result.recalled_tokens += int(event.get("tokens") or 0)
                frames = event.get("frames") or []
                result.recalled_frames += len(frames)
                result.recall_methods.extend(
                    f.get("method") for f in frames if f.get("method")
                )
            elif kind == "memory_citation":
                result.cited_frames += 1

    result.passed, result.detail = score(task, workspace, sandbox)
    if learn and store is not None:
        harvest_store(workspace, store)
    return result
