"""Deterministic verifier for exp-09-zero. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'zero')
    assert_minor_units(ws)
    assert_validates(ws, 'zero')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "zero", "--account", "alice")
    if rc != 0:
        raise VerifyFailure(f"zero failed: rc={rc} err={err!r}")
    if out != "zeroed alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 0:
        raise VerifyFailure(f"alice should be 0, got {data['accounts']['alice']!r}")
    entries = [e for e in data["journal"] if e.get("type") == "zero"]
    if not entries:
        raise VerifyFailure("no journal entry with type 'zero'")
    if entries[-1].get("amount") != 10000:
        raise VerifyFailure(f"zero entry amount should be 10000, got {entries[-1].get('amount')!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "zero", "--account", "nobody")
