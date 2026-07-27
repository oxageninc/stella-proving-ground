"""Deterministic verifier for exp-07-rename. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'rename')
    assert_minor_units(ws)
    assert_validates(ws, 'rename')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "rename", "--from", "bob", "--to", "robert")
    if rc != 0:
        raise VerifyFailure(f"rename failed: rc={rc} err={err!r}")
    if out != "renamed bob to robert":
        raise VerifyFailure(f"unexpected output: {out!r}")
    accounts = load_ledger(ws)["accounts"]
    if accounts.get("robert") != 2500 or "bob" in accounts:
        raise VerifyFailure(f"rename did not move the balance: {accounts!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "rename", "--from", "nobody", "--to", "x")
