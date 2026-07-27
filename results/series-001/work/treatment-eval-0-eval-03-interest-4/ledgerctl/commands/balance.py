from ..money import format_amount
from ..validate import require


def run(args: dict, store) -> str:
    require(args, "account")
    minor = store.balance(args["account"])
    return f"{args['account']} {format_amount(minor)}"
