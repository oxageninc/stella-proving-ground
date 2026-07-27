"""Deterministic verifier for exp-01-withdraw. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'withdraw')
    assert_minor_units(ws)
    assert_validates(ws, 'withdraw')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "withdraw", "--account", "alice", "--amount", "5.00")
    if rc != 0:
        raise VerifyFailure(f"withdraw failed: rc={rc} err={err!r}")
    if out != "withdrew 5.00 from alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 9500:
        raise VerifyFailure(f"alice should be 9500, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "withdraw" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'withdraw'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "withdraw", "--account", "bob", "--amount", "999.00")
