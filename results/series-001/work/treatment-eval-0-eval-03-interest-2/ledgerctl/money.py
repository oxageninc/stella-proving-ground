"""Money is integer minor units (cents) everywhere inside the ledger.

Never use float for ledger arithmetic; see CONTRIBUTING.md.
"""

from .errors import ValidationError


def parse_amount(text: str) -> int:
    """'12.50' -> 1250. Rejects anything that is not a plain decimal amount."""
    s = str(text).strip()
    if s.startswith("-"):
        raise ValidationError("amount must not be negative")
    if "." not in s:
        if not s.isdigit():
            raise ValidationError(f"malformed amount: {text!r}")
        return int(s) * 100
    whole, _, frac = s.partition(".")
    if not whole.isdigit() or not frac.isdigit() or len(frac) > 2:
        raise ValidationError(f"malformed amount: {text!r}")
    return int(whole) * 100 + int(frac.ljust(2, "0"))


def format_amount(minor: int) -> str:
    """1250 -> '12.50'."""
    if not isinstance(minor, int):
        raise ValidationError("amounts must be integer minor units")
    return f"{minor // 100}.{minor % 100:02d}"
