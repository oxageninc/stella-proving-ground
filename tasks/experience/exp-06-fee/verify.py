"""Deterministic verifier for exp-06-fee. Mounted read-only at scoring time."""

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
        rc, out, err = run_cli(ws, 'fee', '--account', 'alice', '--amount', '2.01')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'charged 2.01 fee to alice':
            raise VerifyFailure(f"unexpected output: {out!r}")
        rc, out, err = run_cli(ws, 'fee', '--account', 'alice', '--amount', '2.01')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'charged 2.01 fee to alice':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('alice') != 9613:
            raise VerifyFailure(f"alice should be 9613, got {data['accounts'].get('alice')!r}")
        seen = [e for e in data["journal"] if e.get("type") == 'fee']
        if len(seen) != 2:
            raise VerifyFailure(f"expected 2 fee journal entries, got {len(seen)}")

    report.check("registered", lambda: assert_registered(ws, 'fee'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'fee', '--account', 'bob', '--amount', '999.00')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'fee')

    report.check("validated", validated)
    return report
