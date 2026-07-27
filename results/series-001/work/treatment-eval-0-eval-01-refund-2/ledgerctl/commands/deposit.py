from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "amount")
    minor = parse_amount(args["amount"])
    store.credit(args["account"], minor)
    store.post({"type": "deposit", "account": args["account"], "amount": minor})
    return f"deposited {format_amount(minor)} to {args['account']}"
