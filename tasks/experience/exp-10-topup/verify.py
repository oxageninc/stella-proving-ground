"""Deterministic verifier for exp-10-topup. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'topup')
    assert_minor_units(ws)
    assert_validates(ws, 'topup')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "topup", "--account", "bob", "--amount", "7.25")
    if rc != 0:
        raise VerifyFailure(f"topup failed: rc={rc} err={err!r}")
    if out != "topped up bob by 7.25":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["bob"] != 3225:
        raise VerifyFailure(f"bob should be 3225, got {data['accounts']['bob']!r}")
    if not any(e.get("type") == "topup" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'topup'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "topup", "--account", "nobody", "--amount", "1.00")
