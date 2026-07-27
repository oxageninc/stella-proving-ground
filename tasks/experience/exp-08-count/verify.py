"""Deterministic verifier for exp-08-count. Mounted read-only at scoring time."""

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
        rc, out, err = run_cli(ws, 'count')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'accounts 2':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)

    report.check("registered", lambda: assert_registered(ws, 'count'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    return report
