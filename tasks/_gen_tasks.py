#!/usr/bin/env python3
"""Emit the task pools.

Every task is the same shape — add one command to `ledgerctl` — so that the
only thing separating the experience pool from the evaluation pool is *which*
command, never task difficulty or task form. That matters: if eval tasks were
systematically harder, an accuracy gap between arms could be a difficulty
artifact rather than a transfer effect.

Each task emits:
  <pool>/<id>/prompt.md   — what the agent is told, verbatim
  <pool>/<id>/setup.json  — starting ledger state
  <pool>/<id>/verify.py   — deterministic verifier, never in the workspace
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROMPT = """Add a `{name}` command to the ledgerctl CLI in this repository.

{spec}

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
"""

VERIFY_HEAD = '''"""Deterministic verifier for {id}. Mounted read-only at scoring time."""

from pathlib import Path

from verifier_lib import (
    assert_ledger_error,
    assert_minor_units,
    assert_registered,
    assert_validates,
    load_ledger,
    run_cli,
    write_ledger,
    VerifyFailure,
)


def verify(ws: Path) -> None:
'''


def task(pool, tid, name, spec, setup, body):
    d = HERE / pool / tid
    d.mkdir(parents=True, exist_ok=True)
    (d / "prompt.md").write_text(PROMPT.format(name=name, spec=spec.strip()))
    (d / "setup.json").write_text(json.dumps(setup, indent=2) + "\n")
    (d / "verify.py").write_text(VERIFY_HEAD.format(id=tid) + body.rstrip() + "\n")


BASE = {"accounts": {"alice": 10000, "bob": 2500}, "journal": []}


def std(cmd, *present):
    """The four house conventions, checked identically for every task."""
    args = ", ".join(repr(p) for p in present)
    return f"""
    assert_registered(ws, {cmd!r})
    assert_minor_units(ws)
    assert_validates(ws, {cmd!r}{", " + args if args else ""})
"""


# --------------------------------------------------------------------------
# EXPERIENCE POOL — the agent works these; the lifecycle learns from them.
# --------------------------------------------------------------------------

EXPERIENCE = [
    (
        "exp-01-withdraw",
        "withdraw",
        """
`ledgerctl withdraw --account alice --amount 5.00` debits the account and
prints exactly `withdrew 5.00 from alice`. Record a journal entry with
`"type": "withdraw"`. Withdrawing more than the balance must fail cleanly.
""",
        BASE,
        std("withdraw")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "withdraw", "--account", "alice", "--amount", "5.00")
    if rc != 0:
        raise VerifyFailure(f"withdraw failed: rc={rc} err={err!r}")
    if out != "withdrew 5.00 from alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 9500:
        raise VerifyFailure(f"alice should be 9500, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "withdraw" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'withdraw'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "withdraw", "--account", "bob", "--amount", "999.00")
""",
    ),
    (
        "exp-02-open",
        "open",
        """
`ledgerctl open --account carol` creates a new account with a zero balance and
prints exactly `opened carol`. Opening an account that already exists must
fail cleanly.
""",
        BASE,
        std("open")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "open", "--account", "carol")
    if rc != 0:
        raise VerifyFailure(f"open failed: rc={rc} err={err!r}")
    if out != "opened carol":
        raise VerifyFailure(f"unexpected output: {out!r}")
    if load_ledger(ws)["accounts"].get("carol") != 0:
        raise VerifyFailure("carol should exist with balance 0")
    assert_minor_units(ws)
    assert_ledger_error(ws, "open", "--account", "alice")
""",
    ),
    (
        "exp-03-close",
        "close",
        """
`ledgerctl close --account bob` removes an account and prints exactly
`closed bob`. Closing an account with a non-zero balance must fail cleanly.
""",
        BASE,
        std("close")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 0})
    rc, out, err = run_cli(ws, "close", "--account", "bob")
    if rc != 0:
        raise VerifyFailure(f"close failed: rc={rc} err={err!r}")
    if out != "closed bob":
        raise VerifyFailure(f"unexpected output: {out!r}")
    if "bob" in load_ledger(ws)["accounts"]:
        raise VerifyFailure("bob should be gone from accounts")
    assert_minor_units(ws)
    assert_ledger_error(ws, "close", "--account", "alice")
""",
    ),
    (
        "exp-04-list",
        "list",
        """
`ledgerctl list` prints every account name and formatted balance on one line,
sorted by name, joined by `, ` — for the starting ledger exactly
`alice 100.00, bob 25.00`.
""",
        BASE,
        """
    assert_registered(ws, 'list')
    assert_minor_units(ws)
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "list")
    if rc != 0:
        raise VerifyFailure(f"list failed: rc={rc} err={err!r}")
    if out != "alice 100.00, bob 25.00":
        raise VerifyFailure(f"unexpected output: {out!r}")
""",
    ),
    (
        "exp-05-total",
        "total",
        """
`ledgerctl total` prints the sum of every balance as exactly `total 125.00`
for the starting ledger.
""",
        BASE,
        """
    assert_registered(ws, 'total')
    assert_minor_units(ws)
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "total")
    if rc != 0:
        raise VerifyFailure(f"total failed: rc={rc} err={err!r}")
    if out != "total 125.00":
        raise VerifyFailure(f"unexpected output: {out!r}")
""",
    ),
    (
        "exp-06-fee",
        "fee",
        """
`ledgerctl fee --account alice --amount 1.50` debits a service fee and prints
exactly `charged 1.50 fee to alice`. Record a journal entry with
`"type": "fee"`. A fee larger than the balance must fail cleanly.
""",
        BASE,
        std("fee")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "fee", "--account", "alice", "--amount", "1.50")
    if rc != 0:
        raise VerifyFailure(f"fee failed: rc={rc} err={err!r}")
    if out != "charged 1.50 fee to alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 9850:
        raise VerifyFailure(f"alice should be 9850, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "fee" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'fee'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "fee", "--account", "bob", "--amount", "999.00")
""",
    ),
    (
        "exp-07-rename",
        "rename",
        """
`ledgerctl rename --from bob --to robert` renames an account, preserving its
balance, and prints exactly `renamed bob to robert`. Renaming a missing
account, or onto a name that already exists, must fail cleanly.
""",
        BASE,
        std("rename")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "rename", "--from", "bob", "--to", "robert")
    if rc != 0:
        raise VerifyFailure(f"rename failed: rc={rc} err={err!r}")
    if out != "renamed bob to robert":
        raise VerifyFailure(f"unexpected output: {out!r}")
    accounts = load_ledger(ws)["accounts"]
    if accounts.get("robert") != 2500 or "bob" in accounts:
        raise VerifyFailure(f"rename did not move the balance: {accounts!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "rename", "--from", "nobody", "--to", "x")
""",
    ),
    (
        "exp-08-count",
        "count",
        """
`ledgerctl count` prints the number of accounts as exactly `accounts 2` for
the starting ledger.
""",
        BASE,
        """
    assert_registered(ws, 'count')
    assert_minor_units(ws)
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "count")
    if rc != 0:
        raise VerifyFailure(f"count failed: rc={rc} err={err!r}")
    if out != "accounts 2":
        raise VerifyFailure(f"unexpected output: {out!r}")
""",
    ),
    (
        "exp-09-zero",
        "zero",
        """
`ledgerctl zero --account alice` sets an account balance to zero and prints
exactly `zeroed alice`. Record a journal entry with `"type": "zero"` whose
`amount` is the balance that was removed. A missing account must fail cleanly.
""",
        BASE,
        std("zero")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "zero", "--account", "alice")
    if rc != 0:
        raise VerifyFailure(f"zero failed: rc={rc} err={err!r}")
    if out != "zeroed alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 0:
        raise VerifyFailure(f"alice should be 0, got {data['accounts']['alice']!r}")
    entries = [e for e in data["journal"] if e.get("type") == "zero"]
    if not entries:
        raise VerifyFailure("no journal entry with type 'zero'")
    if entries[-1].get("amount") != 10000:
        raise VerifyFailure(f"zero entry amount should be 10000, got {entries[-1].get('amount')!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "zero", "--account", "nobody")
""",
    ),
    (
        "exp-10-topup",
        "topup",
        """
`ledgerctl topup --account bob --amount 7.25` credits an account and prints
exactly `topped up bob by 7.25`. Record a journal entry with
`"type": "topup"`. A missing account must fail cleanly.
""",
        BASE,
        std("topup")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "topup", "--account", "bob", "--amount", "7.25")
    if rc != 0:
        raise VerifyFailure(f"topup failed: rc={rc} err={err!r}")
    if out != "topped up bob by 7.25":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["bob"] != 3225:
        raise VerifyFailure(f"bob should be 3225, got {data['accounts']['bob']!r}")
    if not any(e.get("type") == "topup" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'topup'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "topup", "--account", "nobody", "--amount", "1.00")
""",
    ),
]

# --------------------------------------------------------------------------
# EVALUATION POOL — held out. Measured, never learned from.
#
# Command names, journal types and output strings here appear nowhere in the
# experience pool; that disjointness is what the leakage gate scans for.
# --------------------------------------------------------------------------

EVALUATION = [
    (
        "eval-01-refund",
        "refund",
        """
`ledgerctl refund --account alice --amount 2.50` debits the account and prints
exactly `refunded 2.50 from alice`. Record a journal entry with
`"type": "refund"`. Refunding more than the balance must fail cleanly.
""",
        BASE,
        std("refund")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "refund", "--account", "alice", "--amount", "2.50")
    if rc != 0:
        raise VerifyFailure(f"refund failed: rc={rc} err={err!r}")
    if out != "refunded 2.50 from alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 9750:
        raise VerifyFailure(f"alice should be 9750, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "refund" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'refund'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "refund", "--account", "bob", "--amount", "999.00")
""",
    ),
    (
        "eval-02-sweep",
        "sweep",
        """
`ledgerctl sweep --from alice --to bob` moves the entire balance of one
account into another, leaving the source at zero, and prints exactly
`swept 100.00 from alice to bob`. Record a journal entry with
`"type": "sweep"`. A missing account must fail cleanly.
""",
        BASE,
        std("sweep")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "sweep", "--from", "alice", "--to", "bob")
    if rc != 0:
        raise VerifyFailure(f"sweep failed: rc={rc} err={err!r}")
    if out != "swept 100.00 from alice to bob":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 0 or data["accounts"]["bob"] != 12500:
        raise VerifyFailure(f"balances wrong after sweep: {data['accounts']!r}")
    if not any(e.get("type") == "sweep" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'sweep'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "sweep", "--from", "nobody", "--to", "bob")
""",
    ),
    (
        "eval-03-interest",
        "interest",
        """
`ledgerctl interest --account alice --rate 5` credits 5 percent of the current
balance and prints exactly `credited 5.00 interest to alice`. Record a journal
entry with `"type": "interest"`. Any fraction of a cent is discarded (round
down). A missing account must fail cleanly.
""",
        BASE,
        std("interest")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "interest", "--account", "alice", "--rate", "5")
    if rc != 0:
        raise VerifyFailure(f"interest failed: rc={rc} err={err!r}")
    if out != "credited 5.00 interest to alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"]["alice"] != 10500:
        raise VerifyFailure(f"alice should be 10500, got {data['accounts']['alice']!r}")
    if not any(e.get("type") == "interest" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'interest'")
    assert_minor_units(ws)
    # Rounding down must not leave a float behind: 3 percent of 2500 is 75.
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "interest", "--account", "bob", "--rate", "3")
    if rc != 0:
        raise VerifyFailure(f"interest (rate 3) failed: rc={rc} err={err!r}")
    data = load_ledger(ws)
    if data["accounts"]["bob"] != 2575:
        raise VerifyFailure(f"bob should be 2575, got {data['accounts']['bob']!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "interest", "--account", "nobody", "--rate", "5")
""",
    ),
    (
        "eval-04-split",
        "split",
        """
`ledgerctl split --from alice --to bob,carol --amount 10.01` debits the source
once and divides the amount as evenly as possible across the comma-separated
destination accounts, giving any leftover minor units to the first
destination. It prints exactly `split 10.01 from alice across 2 accounts`.
Record one journal entry with `"type": "split"`. A missing account must fail
cleanly.
""",
        {"accounts": {"alice": 10000, "bob": 2500, "carol": 0}, "journal": []},
        std("split")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500, "carol": 0})
    rc, out, err = run_cli(ws, "split", "--from", "alice", "--to", "bob,carol", "--amount", "10.01")
    if rc != 0:
        raise VerifyFailure(f"split failed: rc={rc} err={err!r}")
    if out != "split 10.01 from alice across 2 accounts":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    got = data["accounts"]
    # 1001 minor units across two accounts: 501 to the first, 500 to the second.
    if got["alice"] != 8999 or got["bob"] != 3001 or got["carol"] != 500:
        raise VerifyFailure(f"split distribution wrong: {got!r}")
    if not any(e.get("type") == "split" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'split'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "split", "--from", "alice", "--to", "nobody", "--amount", "1.00")
""",
    ),
    (
        "eval-05-statement",
        "statement",
        """
`ledgerctl statement --account alice` prints the account's balance and how
many journal entries mention it, as exactly `alice 100.00 (2 entries)` for a
ledger where two entries reference alice. An entry mentions an account if any
of its values equals the account name. A missing account must fail cleanly.
""",
        BASE,
        std("statement")
        + """
    journal = [
        {"type": "deposit", "account": "alice", "amount": 100},
        {"type": "transfer", "from": "alice", "to": "bob", "amount": 50},
        {"type": "deposit", "account": "bob", "amount": 25},
    ]
    write_ledger(ws, {"alice": 10000, "bob": 2500}, journal)
    rc, out, err = run_cli(ws, "statement", "--account", "alice")
    if rc != 0:
        raise VerifyFailure(f"statement failed: rc={rc} err={err!r}")
    if out != "alice 100.00 (2 entries)":
        raise VerifyFailure(f"unexpected output: {out!r}")
    assert_minor_units(ws)
    assert_ledger_error(ws, "statement", "--account", "nobody")
""",
    ),
    (
        "eval-06-merge",
        "merge",
        """
`ledgerctl merge --from bob --to alice` moves the source account's whole
balance into the destination, removes the source account, and prints exactly
`merged bob into alice`. Record a journal entry with `"type": "merge"`.
Merging a missing account, or an account into itself, must fail cleanly.
""",
        BASE,
        std("merge")
        + """
    write_ledger(ws, {"alice": 10000, "bob": 2500})
    rc, out, err = run_cli(ws, "merge", "--from", "bob", "--to", "alice")
    if rc != 0:
        raise VerifyFailure(f"merge failed: rc={rc} err={err!r}")
    if out != "merged bob into alice":
        raise VerifyFailure(f"unexpected output: {out!r}")
    data = load_ledger(ws)
    if data["accounts"].get("alice") != 12500 or "bob" in data["accounts"]:
        raise VerifyFailure(f"merge left the wrong state: {data['accounts']!r}")
    if not any(e.get("type") == "merge" for e in data["journal"]):
        raise VerifyFailure("no journal entry with type 'merge'")
    assert_minor_units(ws)
    assert_ledger_error(ws, "merge", "--from", "nobody", "--to", "alice")
""",
    ),
]


def main() -> None:
    for tid, name, spec, setup, body in EXPERIENCE:
        task("experience", tid, name, spec, setup, body)
    for tid, name, spec, setup, body in EVALUATION:
        task("evaluation", tid, name, spec, setup, body)
    print(f"wrote {len(EXPERIENCE)} experience + {len(EVALUATION)} evaluation tasks")


if __name__ == "__main__":
    main()
