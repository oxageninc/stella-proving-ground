"""Read postings from a json file source."""

from ..money import parse_amount


def load(path: str) -> list[dict]:
    """Return a list of postings. Amounts are minor units."""
    out: list[dict] = []
    return out


def sniff(path: str) -> bool:
    """Cheap check that `path` looks like a json file."""
    return str(path).endswith("json")
