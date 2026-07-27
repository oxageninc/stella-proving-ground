"""Deterministic verifier for exp-03-close. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'close')
    assert_minor_units(ws)
    assert_validates(ws, 'close')

    write_ledger(ws, {"alice": 10000, "bob": 0})
    rc, out, err = run_cli(ws, "close", "--account", "bob")
    if rc != 0:
        raise VerifyFailure(f"close failed: rc={rc} err={err!r}")
    if out != "closed bob":
        raise VerifyFailure(f"unexpected output: {out!r}")
    if "bob" in load_ledger(ws)["accounts"]:
        raise VerifyFailure("bob should be gone from accounts")
    assert_minor_units(ws)
    assert_ledger_error(ws, "close", "--account", "alice")
