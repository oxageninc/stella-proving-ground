"""Deterministic verifier for exp-07-rename. Mounted read-only at scoring time."""

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
JOURNAL = []


def _seed(ws: Path) -> None:
    """Known state before every stateful check — never the agent's leftovers."""
    write_ledger(ws, ACCOUNTS, JOURNAL)


def verify(ws: Path) -> CheckReport:
    report = CheckReport(ws)

    def behaviour():
        _seed(ws)
        rc, out, err = run_cli(ws, 'rename', '--from', 'bob', '--to', 'robert')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'renamed bob to robert':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('robert') != 2500:
            raise VerifyFailure(f"robert should be 2500, got {data['accounts'].get('robert')!r}")
        if 'bob' in data["accounts"]:
            raise VerifyFailure("bob should be gone")

    report.check("registered", lambda: assert_registered(ws, 'rename'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'rename', '--from', 'nobody', '--to', 'x')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'rename')

    report.check("validated", validated)
    return report
