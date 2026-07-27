"""Both halves of the verifier control, plus the leakage gate's own control.

These tests are the reason any number in this repo is worth reading. They cost
nothing to run — no model, no network — and they fail loudly if the measuring
instrument stops being able to tell a solved task from an unsolved one.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proving_ground.leakage import eval_signature, scan  # noqa: E402
from proving_ground.tasks import load_pool, materialize, score  # noqa: E402
from tests.reference_solutions import apply  # noqa: E402

ALL_TASKS = load_pool("experience") + load_pool("evaluation")


@pytest.mark.parametrize("task", ALL_TASKS, ids=lambda t: t.task_id)
def test_verifier_fails_on_untouched_corpus(task, tmp_path):
    """Negative control: no verifier may pass for free.

    A verifier that passes against the corpus as shipped would score every arm
    at 100% and hide the experiment entirely.
    """
    ws = tmp_path / "ws"
    materialize(task, ws)
    passed, detail, _ = score(task, ws, tmp_path / "sandbox")
    assert not passed, f"{task.task_id} passed without any implementation"
    assert detail, "a failing verifier must say why"


@pytest.mark.parametrize("task", ALL_TASKS, ids=lambda t: t.task_id)
def test_verifier_passes_on_reference_solution(task, tmp_path):
    """Positive control: every task must be winnable.

    An unsatisfiable verifier scores every arm at zero and is indistinguishable
    from a null result, which is the most expensive way to be wrong here.
    """
    ws = tmp_path / "ws"
    materialize(task, ws)
    apply(ws, task.command)
    passed, detail, _ = score(task, ws, tmp_path / "sandbox")
    assert passed, f"{task.task_id} not winnable by the reference solution: {detail}"


def test_pools_are_disjoint():
    """Nothing in the evaluation pool may also be an experience task."""
    experience = {t.command for t in load_pool("experience")}
    evaluation = {t.command for t in load_pool("evaluation")}
    assert not (experience & evaluation)


def _store_with(tmp_path: Path, bodies: list[str]) -> Path:
    store = tmp_path / "store"
    store.mkdir()
    con = sqlite3.connect(store / "context.db")
    con.execute("create table memory (id integer primary key, body text)")
    con.executemany("insert into memory (body) values (?)", [(b,) for b in bodies])
    con.commit()
    con.close()
    return store


def test_leak_signature_is_non_empty():
    """A signature that derived to nothing would make the gate unfireable."""
    signature = eval_signature()
    assert signature
    for task_id, grams in signature.items():
        assert grams, f"{task_id} contributed no evaluation-only n-grams"


def test_gate_is_clean_on_legitimate_experience(tmp_path):
    """Negative control: experience content must not trip the gate."""
    bodies = [t.prompt for t in load_pool("experience")]
    bodies.append("always register the handler in registry.py")
    bodies.append("money is integer minor units, never a float")
    report = scan(_store_with(tmp_path, bodies))
    assert report.clean, report.hits[:3]


def test_gate_fires_on_a_leaked_prompt(tmp_path):
    """Positive control: a whole evaluation prompt must be caught."""
    leaked = load_pool("evaluation")[0]
    bodies = [t.prompt for t in load_pool("experience")] + [leaked.prompt]
    report = scan(_store_with(tmp_path, bodies))
    assert not report.clean
    assert any(h["task_id"] == leaked.task_id for h in report.hits)


def test_gate_fires_on_a_single_distinctive_string(tmp_path):
    """Positive control: leakage does not have to be a whole prompt.

    The realistic failure is one remembered output line, not a pasted task.
    """
    bodies = [t.prompt for t in load_pool("experience")]
    bodies.append("remember: it prints swept 100.00 from alice to bob when done")
    report = scan(_store_with(tmp_path, bodies))
    assert not report.clean
    assert any(h["task_id"] == "eval-02-sweep" for h in report.hits)


def test_corpus_is_pristine():
    """The committed corpus must not contain any pool task's command.

    A trial that edits the corpus hands every later trial of that task a free
    pass, and the edit survives in git if it lands during a `git add -A`. This
    is the standing check that it has not happened.
    """
    from proving_ground.tasks import CORPUS

    registry = (CORPUS / "ledgerctl" / "registry.py").read_text()
    handlers = {p.stem for p in (CORPUS / "ledgerctl" / "commands").glob("*.py")}
    assert handlers == {"__init__", "balance", "deposit", "transfer"}, handlers
    for task in ALL_TASKS:
        assert f'"{task.command}"' not in registry, (
            f"corpus registry contains {task.command!r} — the corpus has been "
            f"contaminated by a trial"
        )


def test_a_partial_arm_epoch_is_not_scored():
    """A cell that does not cover the whole pool must be dropped, not averaged.

    A run stopped mid-cell leaves a partial arm-epoch behind. Scored as if it
    were complete it yields a confident-looking number from almost no data —
    observed live as `treatment - sham = -0.800` with a zero-width CI, computed
    from one trial of one task.
    """
    from proving_ground.stats import summarize

    rows = []
    for task in ("a", "b", "c"):
        for arm in ("treatment", "control"):
            rows.append(
                {"pool": "evaluation", "arm": arm, "epoch": 0, "task_id": task,
                 "passed": True, "input_tokens": 1, "output_tokens": 1,
                 "model_calls": 1, "cost_usd": 0.0, "wall_clock_s": 1.0,
                 "recalled_tokens": 0, "recalled_frames": 0, "cited_frames": 0,
                 "store_stats": {"memories": 0}}
            )
    # A partial cell: one arm covers only one of the three tasks.
    rows.append(
        {"pool": "evaluation", "arm": "sham", "epoch": 0, "task_id": "a",
         "passed": False, "input_tokens": 1, "output_tokens": 1,
         "model_calls": 1, "cost_usd": 0.0, "wall_clock_s": 1.0,
         "recalled_tokens": 0, "recalled_frames": 0, "cited_frames": 0,
         "store_stats": {"memories": 0}}
    )
    summary = summarize(rows)
    assert ("treatment", 0) in summary
    assert ("sham", 0) not in summary, "a partial arm-epoch must not be scored"
