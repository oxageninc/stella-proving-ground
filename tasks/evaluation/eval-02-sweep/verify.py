"""Deterministic verifier for eval-02-sweep. Mounted read-only at scoring time."""

from pathlib import Path

from verifier_lib import (
    CheckReport,
    assert_ledger_error,
    assert_minor_units,
    assert_registered,
    assert_validates,
    load_ledger,
    run_cli,
    write_ledger,
    VerifyFailure,
)

ACCOUNTS = {"alice": 10015, "bob": 2537}
JOURNAL = []


def _seed(ws: Path) -> None:
    """Known state before every stateful check — never the agent's leftovers."""
    write_ledger(ws, ACCOUNTS, JOURNAL)


def verify(ws: Path) -> CheckReport:
    report = CheckReport(ws)

    def behaviour():
        _seed(ws)
        rc, out, err = run_cli(ws, 'sweep', '--from', 'alice', '--to', 'bob')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'swept 100.15 from alice to bob':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('alice') != 0:
            raise VerifyFailure(f"alice should be 0, got {data['accounts'].get('alice')!r}")
        if data["accounts"].get('bob') != 12552:
            raise VerifyFailure(f"bob should be 12552, got {data['accounts'].get('bob')!r}")
        if not any(e.get("type") == 'sweep' for e in data["journal"]):
            raise VerifyFailure("no journal entry with type sweep")

    report.check("registered", lambda: assert_registered(ws, 'sweep'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'sweep', '--from', 'nobody', '--to', 'bob')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'sweep')

    report.check("validated", validated)
    return report
