"""The effort and steering outcomes, and the traps they are built to avoid.

Finding 12: three prior series concluded "no effect" while scoring one bit per
trial. Re-scored on effort, the same trials showed a quarter fewer model calls
and a third less money. These tests pin the pieces of that re-scoring that are
easy to get quietly wrong — every one of them corresponds to a way of producing
a number that looks fine and means nothing.

Free to run: no model, no network, synthetic rows only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proving_ground.scoreboard import render  # noqa: E402
from proving_ground.stats import (  # noqa: E402
    CONTINUOUS_OUTCOMES,
    EFFORT_OUTCOMES,
    OUTCOMES_BY_KEY,
    STEERING_OUTCOME,
    continuous_verdict,
    family_wise_error,
    paired,
    paired_outcome,
    per_task_outcome,
    summarize,
    verdict,
)


def row(
    task_id="eval-01",
    arm="control",
    epoch=0,
    *,
    passed=True,
    status="completed",
    calls=10,
    cost=0.01,
    out_tokens=100,
    error="",
    pool="evaluation",
    trial=0,
):
    return {
        "task_id": task_id,
        "pool": pool,
        "arm": arm,
        "epoch": epoch,
        "trial": trial,
        "passed": passed,
        "detail": "",
        "cost_usd": cost,
        "model_calls": calls,
        "input_tokens": 1000,
        "output_tokens": out_tokens,
        "cached_input_tokens": 0,
        "wall_clock_s": 1.0,
        "recalled_tokens": 0,
        "recalled_frames": 0,
        "recall_methods": [],
        "cited_frames": 0,
        "checks": {},
        "destroyed_workspace": False,
        "models_observed": [],
        "status": status,
        "stella_error": error,
        "config": {},
    }


# --------------------------------------------------------------- the filter


def test_effort_outcomes_ignore_aborted_trials():
    """The trap: an abort truncates a run and so records less effort.

    Counting it would reward whichever arm quits more, which is the opposite of
    what an efficiency number is supposed to mean.
    """
    trials = [
        row(calls=100, status="completed"),
        row(calls=2, status="aborted", trial=1),
    ]
    got = per_task_outcome(trials, OUTCOMES_BY_KEY["model_calls"])
    assert got == {"eval-01": 100.0}, "the aborted trial must not drag the mean down"


def test_steering_is_scored_over_all_trials():
    """The mirror trap: looping is only visible on runs that went wrong.

    Restricting the steering outcome to completed trials would filter out
    precisely the trials it exists to count, and report a flat zero.
    """
    trials = [
        row(status="completed"),
        row(status="aborted", error="stuck-loop detected (persisted after a steer)", trial=1),
    ]
    got = per_task_outcome(trials, STEERING_OUTCOME)
    assert got == {"eval-01": 0.5}, "the aborted, looping trial is the signal"


def test_every_effort_outcome_is_completed_only_and_steering_is_not():
    assert all(o.completed_only for o in EFFORT_OUTCOMES)
    assert not STEERING_OUTCOME.completed_only


def test_stuck_loop_matches_the_harness_wording_and_nothing_else():
    extract = STEERING_OUTCOME.extract
    assert extract(row(error="stuck-loop detected (persisted after a steer)")) == 1.0
    assert extract(row(error="reached the step cap (200) without completing")) == 0.0
    assert extract(row(error="")) == 0.0
    assert extract({"stella_error": None}) == 0.0


def test_a_task_with_no_completed_trials_is_absent_not_zero():
    """Absent, so a paired contrast drops it from both arms.

    Scoring it as 0 would read as "this task cost nothing", which is the most
    flattering possible reading of a task that never finished.
    """
    trials = [
        row(task_id="eval-01", calls=40, status="completed"),
        row(task_id="eval-02", calls=5, status="aborted"),
    ]
    got = per_task_outcome(trials, OUTCOMES_BY_KEY["model_calls"])
    assert set(got) == {"eval-01"}


# ------------------------------------------------------------------ pairing


def _summary(rows):
    return summarize(rows, require_full_coverage=False)


def test_paired_outcome_computes_the_per_task_delta():
    rows = [
        row(task_id="eval-01", arm="treatment", calls=20),
        row(task_id="eval-02", arm="treatment", calls=30),
        row(task_id="eval-01", arm="control", calls=50),
        row(task_id="eval-02", arm="control", calls=40),
    ]
    c = paired_outcome(_summary(rows), 0, "treatment", "control", "model_calls")
    assert c is not None
    # (20-50) and (30-40) -> mean -20
    assert c.delta == -20.0
    assert c.n_tasks == 2
    assert c.baseline == 45.0
    assert abs(c.relative - (-20.0 / 45.0)) < 1e-12
    assert c.outcome == "model_calls"


def test_pairing_uses_only_tasks_present_in_both_arms():
    """A task the completed filter emptied in one arm leaves the contrast."""
    rows = [
        row(task_id="eval-01", arm="treatment", calls=20),
        row(task_id="eval-02", arm="treatment", calls=30),
        row(task_id="eval-01", arm="control", calls=50),
        row(task_id="eval-02", arm="control", calls=999, status="aborted"),
    ]
    c = paired_outcome(_summary(rows), 0, "treatment", "control", "model_calls")
    assert c is not None
    assert c.n_tasks == 1 and set(c.per_task_delta) == {"eval-01"}
    assert c.delta == -30.0


def test_paired_outcome_returns_none_when_an_arm_is_missing():
    rows = [row(arm="treatment")]
    assert paired_outcome(_summary(rows), 0, "treatment", "control", "model_calls") is None


def test_identical_arms_produce_a_zero_delta_that_spans_zero():
    rows = [
        row(task_id=f"eval-0{i}", arm=arm, calls=20 + i)
        for i in (1, 2, 3)
        for arm in ("treatment", "control")
    ]
    c = paired_outcome(_summary(rows), 0, "treatment", "control", "model_calls")
    assert c.delta == 0.0
    assert not c.significant
    assert "within noise" in c.verdict()


def test_a_clean_effort_win_excludes_zero():
    rows = [
        row(task_id=f"eval-0{i}", arm="treatment", calls=10)
        for i in range(1, 7)
    ] + [
        row(task_id=f"eval-0{i}", arm="control", calls=40)
        for i in range(1, 7)
    ]
    c = paired_outcome(_summary(rows), 0, "treatment", "control", "model_calls")
    assert c.delta == -30.0
    assert c.significant
    assert c.verdict() == "CI excludes zero"


def test_continuous_contrasts_never_borrow_the_accuracy_threshold():
    """MIN_MEANINGFUL_EFFECT is 0.10 accuracy points; it means nothing in dollars.

    A cost delta of -0.005 USD is far below 0.10 and must not therefore be
    reported as "below the pre-registered threshold".
    """
    rows = [
        row(task_id=f"eval-0{i}", arm="treatment", cost=0.010) for i in range(1, 7)
    ] + [
        row(task_id=f"eval-0{i}", arm="control", cost=0.015) for i in range(1, 7)
    ]
    c = paired_outcome(_summary(rows), 0, "treatment", "control", "cost_usd")
    assert c.significant and c.meaningful
    assert "threshold" not in c.verdict()


# ---------------------------------------------------- effort != per-solved


def test_effort_per_trial_does_not_move_when_only_accuracy_moves():
    """The reason `*_per_solved` was not reused.

    Both arms do exactly 20 calls per trial. Treatment simply passes more. A
    per-solved ratio reports treatment as far cheaper; per-trial effort — the
    honest answer — reports no difference at all.
    """
    rows = [
        row(task_id=f"eval-0{i}", arm="treatment", calls=20, passed=True)
        for i in range(1, 5)
    ] + [
        row(task_id=f"eval-0{i}", arm="control", calls=20, passed=(i == 1))
        for i in range(1, 5)
    ]
    s = _summary(rows)
    t, c = s[("treatment", 0)], s[("control", 0)]

    assert t.calls_per_solved == 20.0
    assert c.calls_per_solved == 80.0  # 4x, purely from the denominator

    assert t.outcome_mean["model_calls"] == c.outcome_mean["model_calls"] == 20.0
    contrast = paired_outcome(s, 0, "treatment", "control", "model_calls")
    assert contrast.delta == 0.0


# ---------------------------------------------------------------- summarize


def test_summarize_records_completed_and_aborted_counts():
    rows = [
        row(task_id="eval-01", trial=0, status="completed"),
        row(task_id="eval-01", trial=1, status="aborted"),
        row(task_id="eval-01", trial=2, status="timeout"),
    ]
    s = _summary(rows)[("control", 0)]
    assert (s.trials, s.completed, s.aborted) == (3, 1, 2)


def test_summarize_populates_every_continuous_outcome():
    s = _summary([row()])[("control", 0)]
    for o in CONTINUOUS_OUTCOMES:
        assert o.key in s.per_task_outcome
        assert o.key in s.outcome_mean


def test_experience_trials_never_reach_an_effort_number():
    """Same commitment as accuracy: only held-out trials are ever scored."""
    rows = [
        row(task_id="eval-01", calls=10, pool="evaluation"),
        row(task_id="exp-01", calls=999, pool="experience"),
    ]
    s = _summary(rows)[("control", 0)]
    assert s.outcome_mean["model_calls"] == 10.0


# ------------------------------------------------------------------ verdict


def _two_epoch_rows(treatment_calls, control_calls):
    out = []
    for epoch in (0, 1):
        for i in range(1, 7):
            out.append(row(task_id=f"eval-0{i}", arm="treatment", epoch=epoch,
                           calls=treatment_calls))
            out.append(row(task_id=f"eval-0{i}", arm="control", epoch=epoch,
                           calls=control_calls))
            out.append(row(task_id=f"eval-0{i}", arm="sham", epoch=epoch,
                           calls=control_calls))
    return out


def test_continuous_verdict_names_the_axes_that_moved():
    cv = continuous_verdict(_summary(_two_epoch_rows(10, 40)), 1)
    assert "model calls" not in cv["claim"]  # keys, not labels
    assert "model_calls" in cv["claim"]
    assert "cheaper" in cv["claim"]
    assert cv["contrasts"]["treatment-control/model_calls"]["significant"]


def test_continuous_verdict_says_nothing_when_nothing_moved():
    cv = continuous_verdict(_summary(_two_epoch_rows(20, 20)), 1)
    assert "no detectable" in cv["claim"]


def test_verdict_carries_the_continuous_block():
    """The whole point: the top-level verdict cannot be accuracy-blind."""
    v = verdict(_summary(_two_epoch_rows(10, 40)))
    assert "continuous" in v
    assert v["continuous"]["n_contrasts"] > 0


def test_family_wise_error_grows_with_the_family():
    assert family_wise_error(0) == 0.0
    assert abs(family_wise_error(1) - 0.05) < 1e-12
    assert family_wise_error(30) > 0.75
    assert family_wise_error(10) > family_wise_error(5)


# --------------------------------------------------------------- scoreboard


def test_scoreboard_reports_effort_and_steering(tmp_path):
    import json

    path = tmp_path / "results.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in _two_epoch_rows(10, 40)) + "\n"
    )
    md = render(path)

    assert "## Effort per trial (completed trials only)" in md
    assert "## Steering — stuck-loop rate (all trials)" in md
    assert "## Paired contrasts on effort and steering" in md
    assert "family-wise error rate" in md
    # The primary must still be labelled as the primary.
    assert "## Paired comparisons — accuracy (primary)" in md
    # And the misleading ratios must carry their warning.
    assert "conflate effort with correctness" in md


def test_scoreboard_still_renders_a_real_series():
    """Guard against the re-scoring breaking on already-published data."""
    published = Path(__file__).resolve().parent.parent / "results/series-001/results.jsonl"
    if not published.exists():
        return
    md = render(published)
    assert "## Effort per trial (completed trials only)" in md
    assert "contrasts are computed on this page" in md
