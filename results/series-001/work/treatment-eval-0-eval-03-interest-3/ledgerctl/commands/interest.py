from ..money import format_amount, parse_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account", "rate")
    minor = parse_amount(args["rate"])
    balance = store.balance(args["account"])
    interest = (balance * minor) // 100  # 5% of balance, rounded down
    store.credit(args["account"], interest)
    store.post({"type": "interest", "account": args["account"], "amount": interest})
    return f"credited {format_amount(interest)} interest to {args['account']}"