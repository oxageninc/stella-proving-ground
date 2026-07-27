"""Deterministic verifier for exp-08-count. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'count')
    assert_minor_units(ws)
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "count")
    if rc != 0:
        raise VerifyFailure(f"count failed: rc={rc} err={err!r}")
    if out != "accounts 2":
        raise VerifyFailure(f"unexpected output: {out!r}")
