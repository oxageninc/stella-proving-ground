#!/usr/bin/env python3
"""Emit the task pools.

Every task is the same shape — add one command to `ledgerctl` — so that the
only thing separating the experience pool from the evaluation pool is *which*
command, never task difficulty or task form. If evaluation tasks were
systematically harder, an accuracy gap between arms could be a difficulty
artifact rather than a transfer effect.

Each task emits:
  <pool>/<id>/prompt.md   — what the agent is told, verbatim
  <pool>/<id>/setup.json  — starting ledger state
  <pool>/<id>/verify.py   — deterministic verifier, never in the workspace

## Two things every generated verifier now does, learned the hard way

**It seeds before it asserts.** Asserting against whatever the agent left
behind conflated "violated a convention" with "deleted the file": two `sweep`
trials removed `ledger.json` and were reported as `ledger file missing`, which
named no convention and tested none.

**It scores each check separately.** A whole-task bit over six tasks gave the
bootstrap n=6 and a confidence interval wider than the effect it was measuring.
The same trials scored per check yield several times the observations at
identical model cost — and convention compliance is what context is supposed to
teach, so it measures the mechanism rather than a noisy proxy for it.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROMPT = """Add a `{name}` command to the ledgerctl CLI in this repository.

{spec}

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
"""

HEAD = '''"""Deterministic verifier for {id}. Mounted read-only at scoring time."""

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

ACCOUNTS = {accounts}
JOURNAL = {journal}


def _seed(ws: Path) -> None:
    """Known state before every stateful check — never the agent's leftovers."""
    write_ledger(ws, ACCOUNTS, JOURNAL)


def verify(ws: Path) -> CheckReport:
    report = CheckReport(ws)

    def behaviour():
        _seed(ws)
{behaviour}

    report.check("registered", lambda: assert_registered(ws, {cmd!r}))
    report.check("behaviour", behaviour)
    report.check("minor_units", lambda: assert_minor_units(ws))
{extra}
    return report
'''


def emit(pool, tid, name, spec, accounts, journal, behaviour, error_argv=None, validate_args=None):
    d = HERE / pool / tid
    d.mkdir(parents=True, exist_ok=True)
    (d / "prompt.md").write_text(PROMPT.format(name=name, spec=spec.strip()))
    (d / "setup.json").write_text(
        json.dumps({"accounts": accounts, "journal": journal}, indent=2) + "\n"
    )
    extra = []
    if error_argv is not None:
        args = ", ".join(repr(a) for a in error_argv)
        extra.append(
            f"""
    def error_path():
        _seed(ws)
        assert_ledger_error(ws, {args})

    report.check("ledger_error", error_path)"""
        )
    if validate_args is not None:
        args = "".join(f", {a!r}" for a in validate_args)
        extra.append(
            f"""
    def validated():
        _seed(ws)
        assert_validates(ws, {name!r}{args})

    report.check("validated", validated)"""
        )
    (d / "verify.py").write_text(
        HEAD.format(
            id=tid,
            accounts=json.dumps(accounts),
            journal=json.dumps(journal),
            cmd=name,
            behaviour="\n".join("        " + ln for ln in behaviour.strip().splitlines()),
            extra="\n".join(extra),
        )
    )


BASE = {"alice": 10000, "bob": 2500}


def line(cmd_args, expect_out, checks=""):
    """The common behaviour body: run once, assert the output, assert state."""
    args = ", ".join(repr(a) for a in cmd_args)
    body = f"""rc, out, err = run_cli(ws, {args})
if rc != 0:
    raise VerifyFailure(f"rc={{rc}} err={{err!r}}")
if out != {expect_out!r}:
    raise VerifyFailure(f"unexpected output: {{out!r}}")
data = load_ledger(ws)"""
    return body + ("\n" + checks.strip() if checks.strip() else "")


def journal_has(kind):
    return (
        f'if not any(e.get("type") == {kind!r} for e in data["journal"]):\n'
        f'    raise VerifyFailure("no journal entry with type {kind}")'
    )


def bal(acct, want):
    return (
        f'if data["accounts"].get({acct!r}) != {want}:\n'
        f'    raise VerifyFailure(f"{acct} should be {want}, got {{data[\'accounts\'].get({acct!r})!r}}")'
    )


def gone(acct):
    return (
        f'if {acct!r} in data["accounts"]:\n'
        f'    raise VerifyFailure("{acct} should be gone")'
    )


# --------------------------------------------------------------------------
# EXPERIENCE POOL — the agent works these; the lifecycle learns from them.
# --------------------------------------------------------------------------

EXPERIENCE = [
    ("exp-01-withdraw", "withdraw",
     "`ledgerctl withdraw --account alice --amount 5.00` debits the account and prints exactly\n`withdrew 5.00 from alice`. Record a journal entry with `\"type\": \"withdraw\"`.\nWithdrawing more than the balance must fail cleanly.",
     BASE, [], line(["withdraw", "--account", "alice", "--amount", "5.00"], "withdrew 5.00 from alice",
                    bal("alice", 9500) + "\n" + journal_has("withdraw")),
     ["withdraw", "--account", "bob", "--amount", "999.00"], []),
    ("exp-02-open", "open",
     "`ledgerctl open --account carol` creates a new account with a zero balance and prints exactly\n`opened carol`. Opening an account that already exists must fail cleanly.",
     BASE, [], line(["open", "--account", "carol"], "opened carol", bal("carol", 0)),
     ["open", "--account", "alice"], []),
    ("exp-03-close", "close",
     "`ledgerctl close --account bob` removes an account and prints exactly `closed bob`.\nClosing an account with a non-zero balance must fail cleanly.",
     {"alice": 10000, "bob": 0}, [], line(["close", "--account", "bob"], "closed bob", gone("bob")),
     ["close", "--account", "alice"], []),
    ("exp-04-list", "list",
     "`ledgerctl list` prints every account name and formatted balance on one line, sorted by\nname, joined by `, ` — for the starting ledger exactly `alice 100.00, bob 25.00`.",
     BASE, [], line(["list"], "alice 100.00, bob 25.00"), None, None),
    ("exp-05-total", "total",
     "`ledgerctl total` prints the sum of every balance as exactly `total 125.00`.",
     BASE, [], line(["total"], "total 125.00"), None, None),
    ("exp-06-fee", "fee",
     "`ledgerctl fee --account alice --amount 1.50` debits a service fee and prints exactly\n`charged 1.50 fee to alice`. Record a journal entry with `\"type\": \"fee\"`.\nA fee larger than the balance must fail cleanly.",
     BASE, [], line(["fee", "--account", "alice", "--amount", "1.50"], "charged 1.50 fee to alice",
                    bal("alice", 9850) + "\n" + journal_has("fee")),
     ["fee", "--account", "bob", "--amount", "999.00"], []),
    ("exp-07-rename", "rename",
     "`ledgerctl rename --from bob --to robert` renames an account, preserving its balance, and\nprints exactly `renamed bob to robert`. Renaming a missing account must fail cleanly.",
     BASE, [], line(["rename", "--from", "bob", "--to", "robert"], "renamed bob to robert",
                    bal("robert", 2500) + "\n" + gone("bob")),
     ["rename", "--from", "nobody", "--to", "x"], []),
    ("exp-08-count", "count",
     "`ledgerctl count` prints the number of accounts as exactly `accounts 2`.",
     BASE, [], line(["count"], "accounts 2"), None, None),
    ("exp-09-zero", "zero",
     "`ledgerctl zero --account alice` sets a balance to zero and prints exactly `zeroed alice`.\nRecord a journal entry with `\"type\": \"zero\"` whose `amount` is the balance removed.\nA missing account must fail cleanly.",
     BASE, [], line(["zero", "--account", "alice"], "zeroed alice",
                    bal("alice", 0) + "\n" + journal_has("zero")),
     ["zero", "--account", "nobody"], []),
    ("exp-10-topup", "topup",
     "`ledgerctl topup --account bob --amount 7.25` credits an account and prints exactly\n`topped up bob by 7.25`. Record a journal entry with `\"type\": \"topup\"`.\nA missing account must fail cleanly.",
     BASE, [], line(["topup", "--account", "bob", "--amount", "7.25"], "topped up bob by 7.25",
                    bal("bob", 3225) + "\n" + journal_has("topup")),
     ["topup", "--account", "nobody", "--amount", "1.00"], []),
]

# --------------------------------------------------------------------------
# EVALUATION POOL — held out. Measured, never learned from.
#
# Weighted toward tasks whose arithmetic *requires* the minor-units
# convention: percentages, division and remainders are where a float
# implementation passes a casual reading and corrupts the ledger. `interest`
# scored 0/25 across every arm lacking that convention and non-zero with it,
# which is the signal shape worth having more of.
# --------------------------------------------------------------------------

EVALUATION = [
    ("eval-01-refund", "refund",
     "`ledgerctl refund --account alice --amount 2.50` debits the account and prints exactly\n`refunded 2.50 from alice`. Record a journal entry with `\"type\": \"refund\"`.\nRefunding more than the balance must fail cleanly.",
     BASE, [], line(["refund", "--account", "alice", "--amount", "2.50"], "refunded 2.50 from alice",
                    bal("alice", 9750) + "\n" + journal_has("refund")),
     ["refund", "--account", "bob", "--amount", "999.00"], []),
    ("eval-02-sweep", "sweep",
     "`ledgerctl sweep --from alice --to bob` moves the entire balance of one account into\nanother, leaving the source at zero, and prints exactly `swept 100.00 from alice to bob`.\nRecord a journal entry with `\"type\": \"sweep\"`. A missing account must fail cleanly.",
     BASE, [], line(["sweep", "--from", "alice", "--to", "bob"], "swept 100.00 from alice to bob",
                    bal("alice", 0) + "\n" + bal("bob", 12500) + "\n" + journal_has("sweep")),
     ["sweep", "--from", "nobody", "--to", "bob"], []),
    ("eval-03-interest", "interest",
     "`ledgerctl interest --account alice --rate 5` credits 5 percent of the current balance and\nprints exactly `credited 5.00 interest to alice`. Record a journal entry with\n`\"type\": \"interest\"`. Any fraction of a cent is discarded (round down).\nA missing account must fail cleanly.",
     BASE, [], line(["interest", "--account", "alice", "--rate", "5"], "credited 5.00 interest to alice",
                    bal("alice", 10500) + "\n" + journal_has("interest")),
     ["interest", "--account", "nobody", "--rate", "5"], []),
    ("eval-04-split", "split",
     "`ledgerctl split --from alice --to bob,carol --amount 10.01` debits the source once and\ndivides the amount as evenly as possible across the comma-separated destinations, giving any\nleftover minor units to the first. It prints exactly `split 10.01 from alice across 2 accounts`.\nRecord one journal entry with `\"type\": \"split\"`. A missing account must fail cleanly.",
     {"alice": 10000, "bob": 2500, "carol": 0}, [],
     line(["split", "--from", "alice", "--to", "bob,carol", "--amount", "10.01"],
          "split 10.01 from alice across 2 accounts",
          bal("alice", 8999) + "\n" + bal("bob", 3001) + "\n" + bal("carol", 500) + "\n" + journal_has("split")),
     ["split", "--from", "alice", "--to", "nobody", "--amount", "1.00"], []),
    ("eval-05-statement", "statement",
     "`ledgerctl statement --account alice` prints the balance and how many journal entries\nmention it, as exactly `alice 100.00 (2 entries)`. An entry mentions an account if any of\nits values equals the account name. A missing account must fail cleanly.",
     BASE, [{"type": "deposit", "account": "alice", "amount": 100},
            {"type": "transfer", "from": "alice", "to": "bob", "amount": 50},
            {"type": "deposit", "account": "bob", "amount": 25}],
     line(["statement", "--account", "alice"], "alice 100.00 (2 entries)"),
     ["statement", "--account", "nobody"], []),
    ("eval-06-merge", "merge",
     "`ledgerctl merge --from bob --to alice` moves the source's whole balance into the\ndestination, removes the source, and prints exactly `merged bob into alice`.\nRecord a journal entry with `\"type\": \"merge\"`. Merging a missing account, or an account\ninto itself, must fail cleanly.",
     BASE, [], line(["merge", "--from", "bob", "--to", "alice"], "merged bob into alice",
                    bal("alice", 12500) + "\n" + gone("bob") + "\n" + journal_has("merge")),
     ["merge", "--from", "nobody", "--to", "alice"], []),
    # --- convention-heavy additions: arithmetic that punishes floats --------
    ("eval-07-tax", "tax",
     "`ledgerctl tax --account alice --rate 7` debits 7 percent of the balance as tax and prints\nexactly `collected 7.00 tax from alice`. Record a journal entry with `\"type\": \"tax\"`.\nAny fraction of a cent is discarded (round down). A missing account must fail cleanly.",
     BASE, [], line(["tax", "--account", "alice", "--rate", "7"], "collected 7.00 tax from alice",
                    bal("alice", 9300) + "\n" + journal_has("tax")),
     ["tax", "--account", "nobody", "--rate", "7"], []),
    ("eval-08-installments", "installments",
     "`ledgerctl installments --account bob --amount 10.00 --count 3` divides the amount into 3\nparts as evenly as possible in minor units, giving any remainder to the FIRST installment, and\nprints exactly `3 installments of 3.34, 3.33, 3.33`. It changes no balance.\nA count of zero must fail cleanly.",
     BASE, [], line(["installments", "--account", "bob", "--amount", "10.00", "--count", "3"],
                    "3 installments of 3.34, 3.33, 3.33", bal("bob", 2500)),
     ["installments", "--account", "bob", "--amount", "10.00", "--count", "0"], []),
    ("eval-09-reconcile", "reconcile",
     "`ledgerctl reconcile` sums every journal entry's `amount` and prints exactly\n`journal 1.75 across 3 entries` for a ledger whose entries total 175 minor units.\nAn entry without an `amount` counts toward the entry total but adds nothing to the sum.",
     BASE, [{"type": "deposit", "account": "alice", "amount": 100},
            {"type": "fee", "account": "bob", "amount": 75},
            {"type": "note", "account": "alice"}],
     line(["reconcile"], "journal 1.75 across 3 entries"), None, None),
    ("eval-10-cap", "cap",
     "`ledgerctl cap --account alice --max 50.00` reduces a balance to the cap when it exceeds it,\nrecords a journal entry with `\"type\": \"cap\"` whose `amount` is the amount removed, and prints\nexactly `capped alice at 50.00, removed 50.00`. A missing account must fail cleanly.",
     BASE, [], line(["cap", "--account", "alice", "--max", "50.00"], "capped alice at 50.00, removed 50.00",
                    bal("alice", 5000) + "\n" + journal_has("cap")),
     ["cap", "--account", "nobody", "--max", "1.00"], []),
    ("eval-11-share", "share",
     "`ledgerctl share --account alice` prints the account's share of all money as a whole-number\npercentage, rounded down, as exactly `alice holds 80% of 125.00`.\nA missing account must fail cleanly.",
     BASE, [], line(["share", "--account", "alice"], "alice holds 80% of 125.00"),
     ["share", "--account", "nobody"], []),
    ("eval-12-largest", "largest",
     "`ledgerctl largest` prints the account with the highest balance as exactly `alice 100.00`.\nTies break alphabetically.",
     BASE, [], line(["largest"], "alice 100.00"), None, None),
]


def main() -> None:
    for spec in EXPERIENCE:
        emit("experience", *spec)
    for spec in EVALUATION:
        emit("evaluation", *spec)
    print(f"wrote {len(EXPERIENCE)} experience + {len(EVALUATION)} evaluation tasks")


if __name__ == "__main__":
    main()
