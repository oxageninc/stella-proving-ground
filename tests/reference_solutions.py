"""Reference solutions — the positive half of the verifier control.

A verifier that no correct implementation can satisfy scores every arm at zero
and looks exactly like a null result. These solutions exist so that
`test_verifiers.py` can prove each task is winnable before any model is asked
to win it. They are never shown to the agent.

Each entry is the body of `ledgerctl/commands/<name>.py`; the test also patches
`registry.py`, which is the convention the verifier checks for separately.
"""

REFERENCE: dict[str, str] = {
    "withdraw": '''
from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "amount")
    minor = parse_amount(args["amount"])
    store.debit(args["account"], minor)
    store.post({"type": "withdraw", "account": args["account"], "amount": minor})
    return f"withdrew {format_amount(minor)} from {args['account']}"
''',
    "open": '''
from ..errors import ValidationError
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account")
    name = args["account"]
    if name in store.accounts:
        raise ValidationError(f"account already exists: {name}")
    store.accounts[name] = 0
    return f"opened {name}"
''',
    "close": '''
from ..errors import ValidationError
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account")
    name = args["account"]
    if store.balance(name) != 0:
        raise ValidationError(f"cannot close {name}: balance is not zero")
    del store.accounts[name]
    return f"closed {name}"
''',
    "list": '''
from ..money import format_amount


def run(args: dict, store) -> str:
    return ", ".join(
        f"{name} {format_amount(store.accounts[name])}"
        for name in sorted(store.accounts)
    )
''',
    "total": '''
from ..money import format_amount


def run(args: dict, store) -> str:
    return f"total {format_amount(sum(store.accounts.values()))}"
''',
    "fee": '''
from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "amount")
    minor = parse_amount(args["amount"])
    store.debit(args["account"], minor)
    store.post({"type": "fee", "account": args["account"], "amount": minor})
    return f"charged {format_amount(minor)} fee to {args['account']}"
''',
    "rename": '''
from ..errors import UnknownAccount, ValidationError
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "from", "to")
    src, dst = args["from"], args["to"]
    if src not in store.accounts:
        raise UnknownAccount(f"no such account: {src}")
    if dst in store.accounts:
        raise ValidationError(f"account already exists: {dst}")
    store.accounts[dst] = store.accounts.pop(src)
    return f"renamed {src} to {dst}"
''',
    "count": '''
def run(args: dict, store) -> str:
    return f"accounts {len(store.accounts)}"
''',
    "zero": '''
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account")
    name = args["account"]
    removed = store.balance(name)
    store.accounts[name] = 0
    store.post({"type": "zero", "account": name, "amount": removed})
    return f"zeroed {name}"
''',
    "topup": '''
from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "amount")
    minor = parse_amount(args["amount"])
    store.credit(args["account"], minor)
    store.post({"type": "topup", "account": args["account"], "amount": minor})
    return f"topped up {args['account']} by {format_amount(minor)}"
''',
    "refund": '''
from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "amount")
    minor = parse_amount(args["amount"])
    store.debit(args["account"], minor)
    store.post({"type": "refund", "account": args["account"], "amount": minor})
    return f"refunded {format_amount(minor)} from {args['account']}"
''',
    "sweep": '''
from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "from", "to")
    src, dst = args["from"], args["to"]
    minor = store.balance(src)
    store.balance(dst)
    store.debit(src, minor)
    store.credit(dst, minor)
    store.post({"type": "sweep", "from": src, "to": dst, "amount": minor})
    return f"swept {format_amount(minor)} from {src} to {dst}"
''',
    "interest": '''
from ..errors import ValidationError
from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "rate")
    name = args["account"]
    balance = store.balance(name)
    rate_text = str(args["rate"])
    if not rate_text.isdigit():
        raise ValidationError(f"malformed rate: {rate_text!r}")
    earned = balance * int(rate_text) // 100
    store.credit(name, earned)
    store.post({"type": "interest", "account": name, "amount": earned})
    return f"credited {format_amount(earned)} interest to {name}"
''',
    "split": '''
from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "from", "to", "amount")
    src = args["from"]
    targets = [t for t in str(args["to"]).split(",") if t]
    minor = parse_amount(args["amount"])
    for target in targets:
        store.balance(target)
    store.debit(src, minor)
    share, remainder = divmod(minor, len(targets))
    for i, target in enumerate(targets):
        store.credit(target, share + (remainder if i == 0 else 0))
    store.post(
        {"type": "split", "from": src, "to": targets, "amount": minor}
    )
    return f"split {format_amount(minor)} from {src} across {len(targets)} accounts"
''',
    "statement": '''
from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account")
    name = args["account"]
    balance = store.balance(name)
    count = sum(1 for e in store.journal if name in e.values())
    return f"{name} {format_amount(balance)} ({count} entries)"
''',
    "merge": '''
from ..errors import ValidationError
from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "from", "to")
    src, dst = args["from"], args["to"]
    if src == dst:
        raise ValidationError("cannot merge an account into itself")
    minor = store.balance(src)
    store.balance(dst)
    store.credit(dst, minor)
    del store.accounts[src]
    store.post({"type": "merge", "from": src, "to": dst, "amount": minor})
    return f"merged {src} into {dst}"
''',
    "tax": '''
from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "rate")
    name = args["account"]
    balance = store.balance(name)
    collected = balance * int(str(args["rate"])) // 100
    store.debit(name, collected)
    store.post({"type": "tax", "account": name, "amount": collected})
    return f"collected {format_amount(collected)} tax from {name}"
''',
    "installments": '''
from ..errors import ValidationError
from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "amount", "count")
    store.balance(args["account"])
    count = int(str(args["count"]))
    if count <= 0:
        raise ValidationError("count must be a positive whole number")
    minor = parse_amount(args["amount"])
    share, remainder = divmod(minor, count)
    parts = [share + (remainder if i == 0 else 0) for i in range(count)]
    rendered = ", ".join(format_amount(p) for p in parts)
    return f"{count} installments of {rendered}"
''',
    "reconcile": '''
from ..money import format_amount


def run(args: dict, store) -> str:
    total = sum(e.get("amount", 0) or 0 for e in store.journal)
    return f"journal {format_amount(total)} across {len(store.journal)} entries"
''',
    "cap": '''
from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "max")
    name = args["account"]
    ceiling = parse_amount(args["max"])
    balance = store.balance(name)
    removed = max(0, balance - ceiling)
    if removed:
        store.debit(name, removed)
    store.post({"type": "cap", "account": name, "amount": removed})
    return f"capped {name} at {format_amount(ceiling)}, removed {format_amount(removed)}"
''',
    "share": '''
from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account")
    name = args["account"]
    balance = store.balance(name)
    total = sum(store.accounts.values())
    percent = balance * 100 // total if total else 0
    return f"{name} holds {percent}% of {format_amount(total)}"
''',
    "largest": '''
from ..errors import ValidationError
from ..money import format_amount


def run(args: dict, store) -> str:
    if not store.accounts:
        raise ValidationError("no accounts in the ledger")
    name = min(store.accounts, key=lambda n: (-store.accounts[n], n))
    return f"{name} {format_amount(store.accounts[name])}"
''',
}


def apply(workspace, command: str) -> None:
    """Write the reference handler and register it, honouring the conventions."""
    from pathlib import Path

    ws = Path(workspace)
    (ws / "ledgerctl" / "commands" / f"{command}.py").write_text(
        REFERENCE[command].lstrip()
    )
    registry = ws / "ledgerctl" / "registry.py"
    text = registry.read_text()
    text = text.replace(
        "from .commands import balance, deposit, transfer",
        f"from .commands import balance, deposit, transfer, {command} as _{command}",
    ).replace(
        '    "transfer": transfer,\n}',
        f'    "transfer": transfer,\n    "{command}": _{command},\n}}',
    )
    registry.write_text(text)
