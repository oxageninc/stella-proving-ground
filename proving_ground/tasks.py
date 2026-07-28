"""Task pools and the scoring sandbox.

Two pools that are never mixed:

* **experience** — the agent works these; the lifecycle learns from them freely.
* **evaluation** — held out. Measured, never learned from.

A task is a directory holding `prompt.md`, `setup.json` and `verify.py`. The
verifier is deliberately *not* part of the workspace the agent is given; it is
copied into a throwaway scoring sandbox after the agent has stopped. An agent
that cannot read the assertions cannot write code against them.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "tasks" / "corpus" / "ledgerctl"
VERIFIER_LIB = REPO / "tasks" / "verifier_lib.py"


@dataclass(frozen=True)
class Task:
    task_id: str
    pool: str
    directory: Path

    @property
    def prompt(self) -> str:
        return (self.directory / "prompt.md").read_text()

    @property
    def setup(self) -> dict:
        return json.loads((self.directory / "setup.json").read_text())

    @property
    def command(self) -> str:
        """The command this task adds — the identifier the leak scan hunts."""
        return self.task_id.split("-", 2)[2]


def corpus_digest() -> str:
    """Hash the pristine corpus, so tampering with it is detectable.

    Learned the hard way. Trial workspaces originally lived inside this
    repository, and Stella's project-root discovery walks *up* from the working
    directory to the enclosing repo — which put the task definitions, the
    verifiers and the pristine corpus inside the agent's reach. An agent
    working on the `interest` task wrote `interest.py` into
    `tasks/corpus/ledgerctl/`, where the next trial's `materialize` copied it
    out again as though it had shipped that way. Every subsequent trial of that
    task passed for free.

    Workspaces now live outside the repository (see `default_work_root`) and
    this digest is asserted around every trial, because "the agent cannot reach
    the harness" is a property that has to be enforced, not assumed.
    """
    h = hashlib.sha256()
    for path in sorted(CORPUS.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            h.update(str(path.relative_to(CORPUS)).encode())
            h.update(path.read_bytes())
    return h.hexdigest()[:16]


class CorpusTampered(RuntimeError):
    """The pristine corpus changed during a run. Results are not trustworthy."""


def default_work_root(series: str) -> Path:
    """Where trial workspaces live — deliberately outside this repository.

    Anything inside the repo is reachable by an agent whose project root
    resolves to the repo, which is every agent whose cwd is a subdirectory of
    it.
    """
    return Path(tempfile.gettempdir()) / "stella-proving-ground-work" / series


def load_pool(pool: str) -> list[Task]:
    root = REPO / "tasks" / pool
    return [
        Task(task_id=d.name, pool=pool, directory=d)
        for d in sorted(root.iterdir())
        if d.is_dir()
    ]


def materialize(task: Task, dest: Path) -> None:
    """Lay down a pristine corpus plus this task's starting ledger.

    `dest` is the directory the agent works in. The verifier is not here.
    """
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CORPUS, dest)
    (dest / "ledger.json").write_text(json.dumps(task.setup, indent=2) + "\n")


def _purge_corpus_modules() -> None:
    for name in list(sys.modules):
        if name == "ledgerctl" or name.startswith("ledgerctl.") or name == "verifier_lib":
            del sys.modules[name]


def score(task: Task, workspace: Path, sandbox: Path) -> tuple[bool, str, dict]:
    """Run the deterministic verifier against a *copy* of the finished workspace.

    Copying matters twice over: the verifier rewrites `ledger.json` as it walks
    cases, and the agent's `.stella/` store must not be dragged into scoring.

    Returns `(passed, detail)`; `detail` carries the first failing assertion.
    """
    if sandbox.exists():
        shutil.rmtree(sandbox)
    shutil.copytree(workspace, sandbox, ignore=shutil.ignore_patterns(".stella"))
    shutil.copy2(VERIFIER_LIB, sandbox / "verifier_lib.py")
    shutil.copy2(task.directory / "verify.py", sandbox / "_verify.py")

    module_name = f"_verify_{task.task_id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, sandbox / "_verify.py")
    module = importlib.util.module_from_spec(spec)

    sandbox_str = str(sandbox)
    sys.path.insert(0, sandbox_str)
    _purge_corpus_modules()
    try:
        spec.loader.exec_module(module)
        report = module.verify(sandbox)
        # Named checks are the point: one bit per task gave the bootstrap n=6
        # and a CI wider than the effect. A verifier that still raises instead
        # of reporting is treated as a single failed check rather than
        # crashing the trial.
        if report is None:
            return True, "", {}
        return report.passed, report.detail, report.as_dict()
    except Exception as exc:  # noqa: BLE001 — any failure is a task failure
        detail = f"{type(exc).__name__}: {exc}"
        return False, detail[:500], {}
    finally:
        while sandbox_str in sys.path:
            sys.path.remove(sandbox_str)
        _purge_corpus_modules()
