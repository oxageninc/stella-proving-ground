"""Command registry.

`main.py` dispatches only through `COMMANDS`. A handler module that is not
listed here is unreachable. See CONTRIBUTING.md.
"""

from .commands import balance, deposit, refund, transfer

COMMANDS = {
    "balance": balance,
    "deposit": deposit,
    "refund": refund,
    "transfer": transfer,
}
