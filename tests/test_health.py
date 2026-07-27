"""The provider-outage detector, and the failures it must NOT claim.

Written against a real corpse. series-003 recorded 500 trials in about eight
minutes — all aborted, all zero model calls, all `provider transport error` —
and exited 0. Those tests below that reference it read the actual file.

The dangerous direction here is the false positive: a guard that mistakes a run
of genuine agent failures for a dead network would kill a paid run that was
producing exactly the result it was asked for. So the negative controls matter
more than the positive one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proving_ground.health import (  # noqa: E402
    DEFAULT_STREAK,
    is_dead_trial,
    load_tolerant,
    provider_outage,
)

REPO = Path(__file__).resolve().parent.parent
TRANSPORT = (
    "model call failed: provider transport error: error sending request for "
    "url (https://openrouter.ai/api/v1/chat/completions)"
)


def dead(**kw):
    row = {"status": "aborted", "model_calls": 0, "stella_error": TRANSPORT}
    row.update(kw)
    return row


# ------------------------------------------------------------- the positive


def test_a_streak_of_transport_aborts_is_an_outage():
    assert provider_outage([dead() for _ in range(DEFAULT_STREAK)])


def test_one_survivor_in_the_streak_clears_it():
    """The provider came back. That is not an outage, whatever preceded it."""
    rows = [dead() for _ in range(DEFAULT_STREAK * 2)]
    rows[-1] = {"status": "completed", "model_calls": 30, "stella_error": ""}
    assert not provider_outage(rows)


def test_a_short_run_is_never_an_outage():
    assert not provider_outage([dead() for _ in range(DEFAULT_STREAK - 1)])
    assert not provider_outage([])


# ------------------------------------------------- the negatives that matter


def test_genuine_stuck_loops_are_not_an_outage():
    """The most likely false positive: a bad patch making every agent loop.

    That is a result, and killing the run would destroy it.
    """
    loops = [
        {
            "status": "aborted",
            "model_calls": 40,
            "stella_error": "stuck-loop detected (persisted after a steering warning)",
        }
        for _ in range(DEFAULT_STREAK)
    ]
    assert not provider_outage(loops)


def test_step_cap_aborts_are_not_an_outage():
    caps = [
        {
            "status": "aborted",
            "model_calls": 200,
            "stella_error": "reached the step cap (200) without completing",
        }
        for _ in range(DEFAULT_STREAK)
    ]
    assert not provider_outage(caps)


def test_a_transport_error_that_still_made_calls_is_not_an_outage():
    """A mid-run blip on an otherwise working trial is the agent's problem."""
    rows = [dead(model_calls=17) for _ in range(DEFAULT_STREAK)]
    assert not provider_outage(rows)


def test_an_abort_with_no_reason_is_not_an_outage():
    rows = [dead(stella_error="") for _ in range(DEFAULT_STREAK)]
    assert not provider_outage(rows)


def test_is_dead_trial_requires_all_three_conditions():
    assert is_dead_trial(dead())
    assert not is_dead_trial(dead(status="completed"))
    assert not is_dead_trial(dead(model_calls=1))
    assert not is_dead_trial(dead(stella_error="stuck-loop detected"))
    assert not is_dead_trial({})


# ------------------------------------------------------------ reading files


def test_a_half_written_final_line_is_skipped_not_counted(tmp_path):
    """The guard reads the file while the runner is appending to it."""
    path = tmp_path / "results.jsonl"
    path.write_text(
        "\n".join(json.dumps(dead()) for _ in range(DEFAULT_STREAK))
        + "\n" + '{"status": "abo'
    )
    rows = load_tolerant(path)
    assert len(rows) == DEFAULT_STREAK
    assert provider_outage(rows)


def test_load_tolerant_on_a_missing_file_is_empty_not_an_error(tmp_path):
    assert load_tolerant(tmp_path / "nope.jsonl") == []


# ----------------------------------------------------- against real corpses


def test_the_real_outage_trips_it():
    path = REPO / "results/failed-003-provider-outage/results.jsonl"
    if not path.exists():
        return
    assert provider_outage(load_tolerant(path))


def test_the_published_series_do_not_trip_it():
    """Both real series ended with ordinary trials and must be left alone."""
    for name in ("series-001", "series-002"):
        path = REPO / "results" / name / "results.jsonl"
        if not path.exists():
            continue
        assert not provider_outage(load_tolerant(path)), name
