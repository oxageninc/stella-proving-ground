"""Deterministic verifier for eval-09-reconcile. Mounted read-only at scoring time."""

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

ACCOUNTS = {"alice": 10000, "bob": 2500}
JOURNAL = [{"type": "deposit", "account": "alice", "amount": 100}, {"type": "fee", "account": "bob", "amount": 75}, {"type": "note", "account": "alice"}]


def _seed(ws: Path) -> None:
    """Known state before every stateful check — never the agent's leftovers."""
    write_ledger(ws, ACCOUNTS, JOURNAL)


def verify(ws: Path) -> CheckReport:
    report = CheckReport(ws)

    def behaviour():
        _seed(ws)
        rc, out, err = run_cli(ws, 'reconcile')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'journal 1.75 across 3 entries':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)

    report.check("registered", lambda: assert_registered(ws, 'reconcile'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    return report
