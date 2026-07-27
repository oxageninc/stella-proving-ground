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


def fmt(minor: int) -> str:
    """1250 -> '12.50'. Mirrors `money.format_amount` so expected strings in the
    verifiers are computed, never typed. Every expected balance below is derived
    by the same integer arithmetic the corpus uses, which is what stops a task
    from shipping with an arithmetic error in its own answer key."""
    return f"{minor // 100}.{minor % 100:02d}"


#: Starting balances carry odd cents on purpose.
#:
#: With round numbers (100.00 / 25.00) every percentage came out exact, so the
#: "discard fractions of a cent" rule never decided anything and a float
#: implementation scored identically to a correct one. 100.15 and 25.37 make the
#: remainder real: 5% of 10015 is 500.75, and only an implementation that floors
#: in minor units lands on 500.
BASE = {"alice": 10015, "bob": 2537}

#: Amounts whose naive parse is WRONG.
#:
#: `int(float("1.15") * 100)` is 114, not 115 — binary floating point cannot
#: represent 1.15, and truncation takes the error downward. The house helper
#: `money.parse_amount` splits the string instead and returns 115.
#:
#: This is the whole point of the redesign. Before, the minor-units convention
#: was decoration: the agent already stored integers, so the check passed
#: whether or not it understood why. Now the convention decides the *answer* —
#: follow it and the balance is right, hand-roll the parse and it is off by a
#: cent, on every single one of these amounts.
TRAP_115 = "1.15"   # -> 115, naive 114
TRAP_201 = "2.01"   # -> 201, naive 200
TRAP_029 = "0.29"   # ->  29, naive  28
TRAP_230 = "2.30"   # -> 230, naive 229


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


def seq(steps, checks=""):
    """Several invocations in a row, then assert the accumulated state.

    A single invocation cannot tell a correct implementation from one that
    happens to be right once. Running twice catches the implementations that
    re-read stale state, write the whole ledger back from a snapshot taken at
    startup, or compound a rounding error — none of which a one-shot check sees.

    With compounding percentages it is stronger still: the second call's
    expected output depends on the first call having been exactly right, so one
    cent of drift anywhere fails visibly rather than averaging out.
    """
    out = []
    for cmd_args, expect_out in steps:
        args = ", ".join(repr(a) for a in cmd_args)
        out.append(f"""rc, out, err = run_cli(ws, {args})
if rc != 0:
    raise VerifyFailure(f"rc={{rc}} err={{err!r}}")
if out != {expect_out!r}:
    raise VerifyFailure(f"unexpected output: {{out!r}}")""")
    out.append("data = load_ledger(ws)")
    body = "\n".join(out)
    return body + ("\n" + checks.strip() if checks.strip() else "")


def journal_has(kind):
    return (
        f'if not any(e.get("type") == {kind!r} for e in data["journal"]):\n'
        f'    raise VerifyFailure("no journal entry with type {kind}")'
    )


def journal_count(kind, n):
    return (
        f'seen = [e for e in data["journal"] if e.get("type") == {kind!r}]\n'
        f'if len(seen) != {n}:\n'
        f'    raise VerifyFailure(f"expected {n} {kind} journal entries, got {{len(seen)}}")'
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
     f"`ledgerctl withdraw --account alice --amount {TRAP_115}` debits the account and prints exactly\n`withdrew {TRAP_115} from alice`. Record a journal entry with `\"type\": \"withdraw\"`.\nWithdrawing more than the balance must fail cleanly.",
     BASE, [],
     seq([(["withdraw", "--account", "alice", "--amount", TRAP_115], f"withdrew {TRAP_115} from alice")] * 2,
         bal("alice", 10015 - 115 - 115) + "\n" + journal_count("withdraw", 2)),
     ["withdraw", "--account", "bob", "--amount", "999.00"], []),
    ("exp-02-open", "open",
     "`ledgerctl open --account carol` creates a new account with a zero balance and prints exactly\n`opened carol`. Opening an account that already exists must fail cleanly.",
     BASE, [], line(["open", "--account", "carol"], "opened carol", bal("carol", 0)),
     ["open", "--account", "alice"], []),
    ("exp-03-close", "close",
     "`ledgerctl close --account bob` removes an account and prints exactly `closed bob`.\nClosing an account with a non-zero balance must fail cleanly.",
     {"alice": 10015, "bob": 0}, [], line(["close", "--account", "bob"], "closed bob", gone("bob")),
     ["close", "--account", "alice"], []),
    ("exp-04-list", "list",
     f"`ledgerctl list` prints every account name and formatted balance on one line, sorted by\nname, joined by `, ` — for the starting ledger exactly `alice {fmt(10015)}, bob {fmt(2537)}`.",
     BASE, [], line(["list"], f"alice {fmt(10015)}, bob {fmt(2537)}"), None, None),
    ("exp-05-total", "total",
     f"`ledgerctl total` prints the sum of every balance as exactly `total {fmt(12552)}`.",
     BASE, [], line(["total"], f"total {fmt(12552)}"), None, None),
    ("exp-06-fee", "fee",
     f"`ledgerctl fee --account alice --amount {TRAP_201}` debits a service fee and prints exactly\n`charged {TRAP_201} fee to alice`. Record a journal entry with `\"type\": \"fee\"`.\nA fee larger than the balance must fail cleanly.",
     BASE, [],
     seq([(["fee", "--account", "alice", "--amount", TRAP_201], f"charged {TRAP_201} fee to alice")] * 2,
         bal("alice", 10015 - 201 - 201) + "\n" + journal_count("fee", 2)),
     ["fee", "--account", "bob", "--amount", "999.00"], []),
    ("exp-07-rename", "rename",
     "`ledgerctl rename --from bob --to robert` renames an account, preserving its balance, and\nprints exactly `renamed bob to robert`. Renaming a missing account must fail cleanly.",
     BASE, [], line(["rename", "--from", "bob", "--to", "robert"], "renamed bob to robert",
                    bal("robert", 2537) + "\n" + gone("bob")),
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
     f"`ledgerctl topup --account bob --amount {TRAP_029}` credits an account and prints exactly\n`topped up bob by {TRAP_029}`. Record a journal entry with `\"type\": \"topup\"`.\nA missing account must fail cleanly.",
     BASE, [],
     seq([(["topup", "--account", "bob", "--amount", TRAP_029], f"topped up bob by {TRAP_029}")] * 2,
         bal("bob", 2537 + 29 + 29) + "\n" + journal_count("topup", 2)),
     ["topup", "--account", "nobody", "--amount", "1.00"], []),
]

# --------------------------------------------------------------------------
# EVALUATION POOL — held out. Measured, never learned from.
#
# Every money task here is now decided by the minor-units convention rather
# than merely checked for it: the amounts do not survive `float`, and the
# percentages leave a real fraction of a cent to discard. Before this, control
# scored 0.950 on checks with five tasks perfect in every arm — no treatment
# could have shown an effect, because there was nowhere for the score to go.
# --------------------------------------------------------------------------

EVALUATION = [
    ("eval-01-refund", "refund",
     f"`ledgerctl refund --account alice --amount {TRAP_115}` debits the account and prints exactly\n`refunded {TRAP_115} from alice`. Record a journal entry with `\"type\": \"refund\"`.\nRefunding more than the balance must fail cleanly.",
     BASE, [],
     seq([(["refund", "--account", "alice", "--amount", TRAP_115], f"refunded {TRAP_115} from alice")] * 2,
         bal("alice", 10015 - 115 - 115) + "\n" + journal_count("refund", 2)),
     ["refund", "--account", "bob", "--amount", "999.00"], []),
    ("eval-02-sweep", "sweep",
     f"`ledgerctl sweep --from alice --to bob` moves the entire balance of one account into\nanother, leaving the source at zero, and prints exactly `swept {fmt(10015)} from alice to bob`.\nRecord a journal entry with `\"type\": \"sweep\"`. A missing account must fail cleanly.",
     BASE, [], line(["sweep", "--from", "alice", "--to", "bob"], f"swept {fmt(10015)} from alice to bob",
                    bal("alice", 0) + "\n" + bal("bob", 12552) + "\n" + journal_has("sweep")),
     ["sweep", "--from", "nobody", "--to", "bob"], []),
    ("eval-03-interest", "interest",
     f"`ledgerctl interest --account alice --rate 5` credits 5 percent of the current balance and\nprints exactly `credited {fmt(500)} interest to alice` the first time. Record a journal entry with\n`\"type\": \"interest\"`. Any fraction of a cent is discarded (round down), and interest\ncompounds — a second call charges 5 percent of the new balance.\nA missing account must fail cleanly.",
     BASE, [],
     seq([(["interest", "--account", "alice", "--rate", "5"], f"credited {fmt(500)} interest to alice"),
          (["interest", "--account", "alice", "--rate", "5"], f"credited {fmt(525)} interest to alice")],
         bal("alice", 10015 + 500 + 525) + "\n" + journal_count("interest", 2)),
     ["interest", "--account", "nobody", "--rate", "5"], []),
    ("eval-04-split", "split",
     f"`ledgerctl split --from alice --to bob,carol --amount {TRAP_201}` debits the source once and\ndivides the amount as evenly as possible across the comma-separated destinations, giving any\nleftover minor units to the first. It prints exactly `split {TRAP_201} from alice across 2 accounts`.\nRecord one journal entry with `\"type\": \"split\"`. A missing account must fail cleanly.",
     {"alice": 10015, "bob": 2537, "carol": 0}, [],
     line(["split", "--from", "alice", "--to", "bob,carol", "--amount", TRAP_201],
          f"split {TRAP_201} from alice across 2 accounts",
          bal("alice", 10015 - 201) + "\n" + bal("bob", 2537 + 101) + "\n" + bal("carol", 100) + "\n" + journal_has("split")),
     ["split", "--from", "alice", "--to", "nobody", "--amount", "1.00"], []),
    ("eval-05-statement", "statement",
     f"`ledgerctl statement --account alice` prints the balance and how many journal entries\nmention it, as exactly `alice {fmt(10015)} (2 entries)`. An entry mentions an account if any of\nits values equals the account name. A missing account must fail cleanly.",
     BASE, [{"type": "deposit", "account": "alice", "amount": 1015},
            {"type": "transfer", "from": "alice", "to": "bob", "amount": 50},
            {"type": "deposit", "account": "bob", "amount": 25}],
     line(["statement", "--account", "alice"], f"alice {fmt(10015)} (2 entries)"),
     ["statement", "--account", "nobody"], []),
    ("eval-06-merge", "merge",
     "`ledgerctl merge --from bob --to alice` moves the source's whole balance into the\ndestination, removes the source, and prints exactly `merged bob into alice`.\nRecord a journal entry with `\"type\": \"merge\"`. Merging a missing account, or an account\ninto itself, must fail cleanly.",
     BASE, [], line(["merge", "--from", "bob", "--to", "alice"], "merged bob into alice",
                    bal("alice", 12552) + "\n" + gone("bob") + "\n" + journal_has("merge")),
     ["merge", "--from", "nobody", "--to", "alice"], []),
    ("eval-07-tax", "tax",
     f"`ledgerctl tax --account alice --rate 7` debits 7 percent of the balance as tax and prints\nexactly `collected {fmt(701)} tax from alice` the first time. Record a journal entry with\n`\"type\": \"tax\"`. Any fraction of a cent is discarded (round down), and a second call taxes\nthe reduced balance. A missing account must fail cleanly.",
     BASE, [],
     seq([(["tax", "--account", "alice", "--rate", "7"], f"collected {fmt(701)} tax from alice"),
          (["tax", "--account", "alice", "--rate", "7"], f"collected {fmt(651)} tax from alice")],
         bal("alice", 10015 - 701 - 651) + "\n" + journal_count("tax", 2)),
     ["tax", "--account", "nobody", "--rate", "7"], []),
    ("eval-08-installments", "installments",
     f"`ledgerctl installments --account bob --amount {TRAP_230} --count 3` divides the amount into 3\nparts as evenly as possible in minor units, giving any remainder to the FIRST installment, and\nprints exactly `3 installments of {fmt(78)}, {fmt(76)}, {fmt(76)}`. It changes no balance.\nA count of zero must fail cleanly.",
     BASE, [], line(["installments", "--account", "bob", "--amount", TRAP_230, "--count", "3"],
                    f"3 installments of {fmt(78)}, {fmt(76)}, {fmt(76)}", bal("bob", 2537)),
     ["installments", "--account", "bob", "--amount", TRAP_230, "--count", "0"], []),
    ("eval-09-reconcile", "reconcile",
     f"`ledgerctl reconcile` sums every journal entry's `amount` and prints exactly\n`journal {fmt(1752)} across 3 entries` for a ledger whose entries total 1752 minor units.\nAn entry without an `amount` counts toward the entry total but adds nothing to the sum.",
     BASE, [{"type": "deposit", "account": "alice", "amount": 1015},
            {"type": "fee", "account": "bob", "amount": 737},
            {"type": "note", "account": "alice"}],
     line(["reconcile"], f"journal {fmt(1752)} across 3 entries"), None, None),
    ("eval-10-cap", "cap",
     f"`ledgerctl cap --account alice --max 50.00` reduces a balance to the cap when it exceeds it,\nrecords a journal entry with `\"type\": \"cap\"` whose `amount` is the amount removed, and prints\nexactly `capped alice at 50.00, removed {fmt(5015)}`. A missing account must fail cleanly.",
     BASE, [], line(["cap", "--account", "alice", "--max", "50.00"], f"capped alice at 50.00, removed {fmt(5015)}",
                    bal("alice", 5000) + "\n" + journal_has("cap")),
     ["cap", "--account", "nobody", "--max", "1.00"], []),
    ("eval-11-share", "share",
     f"`ledgerctl share --account alice` prints the account's share of all money as a whole-number\npercentage, rounded down, as exactly `alice holds {10015 * 100 // 12552}% of {fmt(12552)}`.\nA missing account must fail cleanly.",
     BASE, [], line(["share", "--account", "alice"], f"alice holds {10015 * 100 // 12552}% of {fmt(12552)}"),
     ["share", "--account", "nobody"], []),
    ("eval-12-largest", "largest",
     f"`ledgerctl largest` prints the account with the highest balance as exactly `alice {fmt(10015)}`.\nTies break alphabetically.",
     BASE, [], line(["largest"], f"alice {fmt(10015)}"), None, None),
]


def main() -> None:
    for spec in EXPERIENCE:
        emit("experience", *spec)
    for spec in EVALUATION:
        emit("evaluation", *spec)
    print(f"wrote {len(EXPERIENCE)} experience + {len(EVALUATION)} evaluation tasks")


if __name__ == "__main__":
    main()
