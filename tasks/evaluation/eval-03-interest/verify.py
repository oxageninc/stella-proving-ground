"""Deterministic verifier for eval-03-interest. Mounted read-only at scoring time."""

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

    assert_registered(ws, 'interest')
    assert_minor_units(ws)
    assert_validates(ws, 'interest')

    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "interest", "--account", "alice", "--rate", "5")
    if rc != 0:
        raise VerifyFailure(f"interest failed: rc={rc} err={err!r}")
    if out != "credited 5.00 interest to alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 10500:
        raise VerifyFailure(f"alice should be 10500, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "interest" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'interest'")
    assert_minor_units(ws)
    # Rounding down must not leave a float behind: 3 percent of 2500 is 75.
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "interest", "--account", "bob", "--rate", "3")
    if rc != 0:
        raise VerifyFailure(f"interest (rate 3) failed: rc={rc} err={err!r}")
    data = load_ledger(ws)
    if data["accounts"]["bob"] != 2575:
        raise VerifyFailure(f"bob should be 2575, got {data['accounts']['bob']!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "interest", "--account", "nobody", "--rate", "5")
