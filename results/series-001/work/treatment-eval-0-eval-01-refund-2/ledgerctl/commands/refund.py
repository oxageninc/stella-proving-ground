from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "amount")
    minor = parse_amount(args["amount"])
    store.debit(args["account"], minor)
    store.post({"type": "refund", "account": args["account"], "amount": minor})
    return f"refunded {format_amount(minor)} from {args['account']}"