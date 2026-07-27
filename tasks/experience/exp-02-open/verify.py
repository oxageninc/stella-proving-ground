"""Deterministic verifier for exp-02-open. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'open')
    assert_minor_units(ws)
    assert_validates(ws, 'open')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "open", "--account", "carol")
    if rc != 0:
        raise VerifyFailure(f"open failed: rc={rc} err={err!r}")
    if out != "opened carol":
        raise VerifyFailure(f"unexpected output: {out!r}")
    if load_ledger(ws)["accounts"].get("carol") != 0:
        raise VerifyFailure("carol should exist with balance 0")
    assert_minor_units(ws)
    assert_ledger_error(ws, "open", "--account", "alice")
