"""Deterministic verifier for eval-02-sweep. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'sweep')
    assert_minor_units(ws)
    assert_validates(ws, 'sweep')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "sweep", "--from", "alice", "--to", "bob")
    if rc != 0:
        raise VerifyFailure(f"sweep failed: rc={rc} err={err!r}")
    if out != "swept 100.00 from alice to bob":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 0 or data["accounts"]["bob"] != 12500:
        raise VerifyFailure(f"balances wrong after sweep: {data['accounts']!r}")
    if not any(e.get("type") == "sweep" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'sweep'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "sweep", "--from", "nobody", "--to", "bob")
