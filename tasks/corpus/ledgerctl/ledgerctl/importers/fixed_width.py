"""Read postings from a fixed width source."""

from ..money import parse_amount


def load(path: str) -> list[dict]:
    """Return a list of postings. Amounts are minor units."""
    out: list[dict] = []
    return out


def sniff(path: str) -> bool:
    """Cheap check that `path` looks like a fixed width."""
    return str(path).endswith("fixed")
