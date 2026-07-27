from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "from", "to", "amount")
    minor = parse_amount(args["amount"])
    store.debit(args["from"], minor)
    store.credit(args["to"], minor)
    store.post(
        {
            "type": "transfer",
            "from": args["from"],
            "to": args["to"],
            "amount": minor,
        }
    )
    return f"transferred {format_amount(minor)} from {args['from']} to {args['to']}"
