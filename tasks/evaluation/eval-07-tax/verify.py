"""Deterministic verifier for eval-07-tax. Mounted read-only at scoring time."""

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
        rc, out, err = run_cli(ws, 'tax', '--account', 'alice', '--rate', '7')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'collected 7.01 tax from alice':
            raise VerifyFailure(f"unexpected output: {out!r}")
        rc, out, err = run_cli(ws, 'tax', '--account', 'alice', '--rate', '7')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'collected 6.51 tax from alice':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('alice') != 8663:
            raise VerifyFailure(f"alice should be 8663, got {data['accounts'].get('alice')!r}")
        seen = [e for e in data["journal"] if e.get("type") == 'tax']
        if len(seen) != 2:
            raise VerifyFailure(f"expected 2 tax journal entries, got {len(seen)}")

    report.check("registered", lambda: assert_registered(ws, 'tax'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'tax', '--account', 'nobody', '--rate', '7')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'tax')

    report.check("validated", validated)
    return report
