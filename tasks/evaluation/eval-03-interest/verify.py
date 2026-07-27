"""Deterministic verifier for eval-03-interest. Mounted read-only at scoring time."""

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
        rc, out, err = run_cli(ws, 'interest', '--account', 'alice', '--rate', '5')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'credited 5.00 interest to alice':
            raise VerifyFailure(f"unexpected output: {out!r}")
        rc, out, err = run_cli(ws, 'interest', '--account', 'alice', '--rate', '5')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'credited 5.25 interest to alice':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('alice') != 11040:
            raise VerifyFailure(f"alice should be 11040, got {data['accounts'].get('alice')!r}")
        seen = [e for e in data["journal"] if e.get("type") == 'interest']
        if len(seen) != 2:
            raise VerifyFailure(f"expected 2 interest journal entries, got {len(seen)}")

    report.check("registered", lambda: assert_registered(ws, 'interest'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'interest', '--account', 'nobody', '--rate', '5')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'interest')

    report.check("validated", validated)
    return report
