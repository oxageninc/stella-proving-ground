"""Command registry.

`main.py` dispatches only through `COMMANDS`. A handler module that is not
listed here is unreachable. See CONTRIBUTING.md.
"""

from .commands import balance, deposit, interest, transfer

COMMANDS = {
    "balance": balance,
    "deposit": deposit,
    "transfer": transfer,
    "interest": interest,
}
