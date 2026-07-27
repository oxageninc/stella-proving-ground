"""Deterministic verifier for eval-05-statement. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'statement')
    assert_minor_units(ws)
    assert_validates(ws, 'statement')

    journal = [
        {"type": "deposit", "account": "alice", "amount": 100},
        {"type": "transfer", "from": "alice", "to": "bob", "amount": 50},
        {"type": "deposit", "account": "bob", "amount": 25},
    ]
    write_ledger(ws, {"alice": 10000, "bob": 2500}, journal)
    rc, out, err = run_cli(ws, "statement", "--account", "alice")
    if rc != 0:
        raise VerifyFailure(f"statement failed: rc={rc} err={err!r}")
    if out != "alice 100.00 (2 entries)":
        raise VerifyFailure(f"unexpected output: {out!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "statement", "--account", "nobody")
