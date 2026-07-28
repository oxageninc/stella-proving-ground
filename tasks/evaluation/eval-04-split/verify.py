"""Deterministic verifier for eval-04-split. Mounted read-only at scoring time."""

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

ACCOUNTS = {"alice": 10015, "bob": 2537, "carol": 0}
JOURNAL = []


def _seed(ws: Path) -> None:
    """Known state before every stateful check — never the agent's leftovers."""
    write_ledger(ws, ACCOUNTS, JOURNAL)


def verify(ws: Path) -> CheckReport:
    report = CheckReport(ws)

    def behaviour():
        _seed(ws)
        rc, out, err = run_cli(ws, 'split', '--from', 'alice', '--to', 'bob,carol', '--amount', '2.01')
        if rc != 0:
            raise VerifyFailure(f"rc={rc} err={err!r}")
        if out != 'split 2.01 from alice across 2 accounts':
            raise VerifyFailure(f"unexpected output: {out!r}")
        data = load_ledger(ws)
        if data["accounts"].get('alice') != 9814:
            raise VerifyFailure(f"alice should be 9814, got {data['accounts'].get('alice')!r}")
        if data["accounts"].get('bob') != 2638:
            raise VerifyFailure(f"bob should be 2638, got {data['accounts'].get('bob')!r}")
        if data["accounts"].get('carol') != 100:
            raise VerifyFailure(f"carol should be 100, got {data['accounts'].get('carol')!r}")
        if not any(e.get("type") == 'split' for e in data["journal"]):
            raise VerifyFailure("no journal entry with type split")

    report.check("registered", lambda: assert_registered(ws, 'split'))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))

    def error_path():
        _seed(ws)
        assert_ledger_error(ws, 'split', '--from', 'alice', '--to', 'nobody', '--amount', '1.00')

    report.check("ledger_error", error_path)

    def validated():
        _seed(ws)
        assert_validates(ws, 'split')

    report.check("validated", validated)
    return report
