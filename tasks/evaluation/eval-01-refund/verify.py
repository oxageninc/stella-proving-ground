"""Deterministic verifier for eval-01-refund. Mounted read-only at scoring time."""

from pathlib import Path

from verifier_lib import (
    assert_ledger_error,
    assert_minor_units,
    assert_registered,
    assert_validates,
    load_ledger,
    run_cli,
    write_ledger,
    VerifyFailure,
)


def verify(ws: Path) -> None:

    assert_registered(ws, 'refund')
    assert_minor_units(ws)
    assert_validates(ws, 'refund')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "refund", "--account", "alice", "--amount", "2.50")
    if rc != 0:
        raise VerifyFailure(f"refund failed: rc={rc} err={err!r}")
    if out != "refunded 2.50 from alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 9750:
        raise VerifyFailure(f"alice should be 9750, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "refund" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'refund'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "refund", "--account", "bob", "--amount", "999.00")
