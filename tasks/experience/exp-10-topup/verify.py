"""Deterministic verifier for exp-10-topup. Mounted read-only at scoring time."""

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
        rc, out, err = run_cli(ws, 'topup', '--account', 'bob', '--amount', '7.25')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'topped up bob by 7.25':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('bob') != 3225:
            raise VerifyFailure(f"bob should be 3225, got {data['accounts'].get('bob')!r}")
        if not any(e.get("type") == 'topup' for e in data["journal"]):
            raise VerifyFailure("no journal entry with type topup")

    report.check("registered", lambda: assert_registered(ws, 'topup'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'topup', '--account', 'nobody', '--amount', '1.00')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'topup')

    report.check("validated", validated)
    return report
