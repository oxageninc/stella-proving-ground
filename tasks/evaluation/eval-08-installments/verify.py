"""Deterministic verifier for eval-08-installments. Mounted read-only at scoring time."""

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
        rc, out, err = run_cli(ws, 'installments', '--account', 'bob', '--amount', '2.30', '--count', '3')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != '3 installments of 0.78, 0.76, 0.76':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('bob') != 2537:
            raise VerifyFailure(f"bob should be 2537, got {data['accounts'].get('bob')!r}")

    report.check("registered", lambda: assert_registered(ws, 'installments'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'installments', '--account', 'bob', '--amount', '2.30', '--count', '0')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'installments')

    report.check("validated", validated)
    return report
