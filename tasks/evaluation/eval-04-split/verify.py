"""Deterministic verifier for eval-04-split. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'split')
    assert_minor_units(ws)
    assert_validates(ws, 'split')

    write_ledger(ws, {"alice": 10000, "bob": 2500, "carol": 0})
    rc, out, err = run_cli(ws, "split", "--from", "alice", "--to", "bob,carol", "--amount", "10.01")
    if rc != 0:
        raise VerifyFailure(f"split failed: rc={rc} err={err!r}")
    if out != "split 10.01 from alice across 2 accounts":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    got = data["accounts"]
    # 1001 minor units across two accounts: 501 to the first, 500 to the second.
    if got["alice"] != 8999 or got["bob"] != 3001 or got["carol"] != 500:
        raise VerifyFailure(f"split distribution wrong: {got!r}")
    if not any(e.get("type") == "split" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'split'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "split", "--from", "alice", "--to", "nobody", "--amount", "1.00")
