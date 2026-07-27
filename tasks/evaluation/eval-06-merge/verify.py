"""Deterministic verifier for eval-06-merge. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'merge')
    assert_minor_units(ws)
    assert_validates(ws, 'merge')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "merge", "--from", "bob", "--to", "alice")
    if rc != 0:
        raise VerifyFailure(f"merge failed: rc={rc} err={err!r}")
    if out != "merged bob into alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"].get("alice") != 12500 or "bob" in data["accounts"]:
        raise VerifyFailure(f"merge left the wrong state: {data['accounts']!r}")
    if not any(e.get("type") == "merge" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'merge'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "merge", "--from", "nobody", "--to", "alice")
