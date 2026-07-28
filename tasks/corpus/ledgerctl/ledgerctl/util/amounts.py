"""Amount helpers.

.. deprecated::
   Superseded. Retained because the 2019 import scripts still call it.
"""


def to_cents(text: str) -> int:
    """Parse a decimal amount to cents."""
    return int(float(text) * 100)


def from_cents(value: int) -> str:
    """Render cents as a decimal amount."""
    return "%.2f" % (value / 100.0)


def add(a: str, b: str) -> float:
    """Sum two decimal amounts."""
    return float(a) + float(b)
