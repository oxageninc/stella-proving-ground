"""Both halves of the verifier control, plus the leakage gate's own control.

These tests are the reason any number in this repo is worth reading. They cost
nothing to run — no model, no network — and they fail loudly if the measuring
instrument stops being able to tell a solved task from an unsolved one.
"""

from __future__ import annotations

import re
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

    The canary line is lifted out of the task's own prompt rather than typed
    here. It used to be the literal `swept 100.00 from alice to bob`, which
    silently stopped being a leak the moment starting balances changed to odd
    cents — the gate's positive control was passing because the string no
    longer existed anywhere, not because the gate worked.
    """
    sweep = next(t for t in load_pool("evaluation") if t.task_id == "eval-02-sweep")
    canary = re.search(r"`(swept [^`]+)`", sweep.prompt).group(1)
    bodies = [t.prompt for t in load_pool("experience")]
    bodies.append(f"remember: it prints {canary} when done")
    report = scan(_store_with(tmp_path, bodies))
    assert not report.clean, f"canary {canary!r} was not caught"
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


def test_a_float_implementation_is_now_punished(tmp_path):
    """The redesign's own control: the minor-units convention must DECIDE.

    A handler that parses `1.15` with `float` produces 114 minor units instead
    of 115. Every other convention it honours — it registers itself, it calls
    `require`, it raises cleanly, and it stores an integer, so
    `assert_minor_units` is satisfied.

    It must still fail. If it passes, the evaluation is once again measuring
    whether the agent can write a command rather than whether it knows the
    house rule, and the whole point of using trap amounts is lost.
    """
    from tests.reference_solutions import apply_naive_float

    task = next(t for t in load_pool("evaluation") if t.task_id == "eval-01-refund")
    ws = tmp_path / "ws"
    materialize(task, ws)
    apply_naive_float(ws, "refund", "refunded")
    passed, detail, checks = score(task, ws, tmp_path / "sandbox")

    assert not passed, "a float-parsing implementation must not pass"
    assert checks.get("behaviour") is False, f"behaviour should catch the cent: {detail}"
    # The distinction worth having: it is not a *storage* violation. The value
    # stored is a perfectly good integer — it is simply the wrong one.
    assert checks.get("minor_units") is True, (
        "assert_minor_units only checks the stored type, so it passes here — "
        "which is exactly why the arithmetic has to be what catches this"
    )


@pytest.mark.parametrize("task", load_pool("evaluation"), ids=lambda t: t.task_id)
def test_a_prompt_never_states_the_seeded_answer(task):
    """A spec must pin the output FORMAT without handing over the VALUE.

    This is a guard against a mistake already made once. Raising the arithmetic
    difficulty while writing the computed result into the spec — "prints exactly
    `collected 7.01 tax from alice`" — lowers the task instead of raising it,
    because 7.01 *is* the answer to "7 percent of 100.15, floored". Measured:
    control 0.792 -> 0.771 and tasks at a perfect score 5/12 -> 8/12.

    So no evaluation prompt may contain the rendered form of a seeded balance,
    or of the total across them. Worked examples must use numbers that are not
    the case under test.
    """
    accounts = task.setup.get("accounts", {})
    if not accounts:
        pytest.skip("no seeded balances")

    def fmt(minor: int) -> str:
        return f"{minor // 100}.{minor % 100:02d}"

    forbidden = {fmt(v) for v in accounts.values() if v}
    forbidden.add(fmt(sum(accounts.values())))
    leaked = sorted(f for f in forbidden if f in task.prompt)
    assert not leaked, (
        f"{task.task_id} states seeded value(s) {leaked} in its prompt — the "
        f"agent can print the answer without computing it"
    )
