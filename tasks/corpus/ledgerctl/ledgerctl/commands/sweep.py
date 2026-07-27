from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "from", "to")
    minor = store.balance(args["from"])
    store.credit(args["to"], minor)
    store.debit(args["from"], minor)
    store.post(
        {
            "type": "sweep",
            "from": args["from"],
            "to": args["to"],
            "amount": minor,
        }
    )
    return f"swept {format_amount(minor)} from {args['from']} to {args['to']}"