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
from .tasks import CorpusTampered, Task, corpus_digest, materialize, score

STORE_DIR = Path(".stella") / "private"


def count_citations(workspace: Path) -> int:
    """How many recalled memories the turn actually cited.

    Reads `store.db.memory_citations` rather than the event stream. The stream
    carries no citation event at all, so an earlier version of this function
    counted a `memory_citation` type that does not exist and reported zero for
    every trial in two full series — indistinguishable from a feedback loop
    that never fires. Measuring the wrong thing is worse than not measuring it,
    because the number looks real.
    """
    db = workspace / STORE_DIR / "store.db"
    if not db.exists():
        return 0
    import sqlite3

    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.DatabaseError:
        return 0
    try:
        return con.execute("select count(*) from memory_citations").fetchone()[0]
    except sqlite3.DatabaseError:
        return 0
    finally:
        con.close()


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
    #: Per-check outcomes — the finer-grained signal. `{"registered": True, ...}`
    checks: dict = field(default_factory=dict)
    #: The agent removed or corrupted state it was given. Counted separately
    #: because it is noise in the dimension being measured, not a convention miss.
    destroyed_workspace: bool = False
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


#: How long to wait between attempts when the provider is unreachable, and how
#: many times to try. Sized for a blip, not an outage: ~2 minutes total, after
#: which `health.provider_outage` still stops the series as designed.
RETRY_BACKOFF_S = (5, 15, 45, 60)


def _is_dead(result: "Trial") -> bool:
    """The trial never reached the model — a transport failure, not an agent one."""
    return (
        result.status != "completed"
        and result.model_calls == 0
        and "transport error" in (result.stella_error or "")
    )


def run_trial(task: Task, **kwargs) -> "Trial":
    """Run one trial, retrying through a transient provider failure.

    Three separate series died today because the provider dropped mid-run:
    every remaining trial was recorded as an aborted, zero-model-call failure,
    which is indistinguishable from the agent collapsing. `health.provider_outage`
    now catches that and stops the run — correct for a real outage, and far too
    blunt for the ten-second blip that caused two of the three.

    Retrying here converts a blip into a delay. A trial that never reached the
    model has cost nothing and produced no evidence, so re-running it changes no
    measurement: this retries *transport failures only*, never a genuine agent
    failure, a timeout, or a stuck loop, all of which are real outcomes and are
    returned untouched on the first attempt.

    If the provider is genuinely down, the attempts drain in about two minutes
    and the trial is returned dead, so the outage guard still fires and still
    stops the series. This narrows what counts as an outage; it does not remove
    the safety net.
    """
    last = None
    for attempt, pause in enumerate((0, *RETRY_BACKOFF_S)):
        if pause:
            time.sleep(pause)
        last = _run_trial_once(task, **kwargs)
        if not _is_dead(last):
            return last
        if attempt < len(RETRY_BACKOFF_S):
            last.stella_error = (
                f"{last.stella_error} [retrying transport failure, "
                f"attempt {attempt + 1}]"
            )[:300]
    return last


def _run_trial_once(
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
    # The agent must not be able to reach the harness. Assert it rather than
    # trusting it: a trial that edits the pristine corpus would silently hand
    # every later trial of that task a free pass.
    before = corpus_digest()
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
        result.passed, result.detail, result.checks = score(task, workspace, sandbox)
        result.destroyed_workspace = "workspace-destroyed" in result.detail
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
    # Citations are NOT an agent event. Reading them off the stream — which
    # this harness did at first, counting a `memory_citation` event that does
    # not exist — makes the count structurally zero and looks exactly like a
    # broken feedback loop. They are rows in `store.db`, so that is where they
    # have to be counted from.
    result.cited_frames = count_citations(workspace)

    after = corpus_digest()
    if after != before:
        raise CorpusTampered(
            f"{task.task_id} ({arm} E{epoch}#{trial_index}) modified the pristine "
            f"corpus: digest {before} -> {after}. Every later trial of this task "
            f"would inherit the change. The series is void."
        )

    result.passed, result.detail, result.checks = score(task, workspace, sandbox)
    result.destroyed_workspace = "workspace-destroyed" in result.detail
    if learn and store is not None:
        harvest_store(workspace, store)
    return result
