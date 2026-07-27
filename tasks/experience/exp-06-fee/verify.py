"""Deterministic verifier for exp-06-fee. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'fee')
    assert_minor_units(ws)
    assert_validates(ws, 'fee')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "fee", "--account", "alice", "--amount", "1.50")
    if rc != 0:
        raise VerifyFailure(f"fee failed: rc={rc} err={err!r}")
    if out != "charged 1.50 fee to alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 9850:
        raise VerifyFailure(f"alice should be 9850, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "fee" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'fee'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "fee", "--account", "bob", "--amount", "999.00")
