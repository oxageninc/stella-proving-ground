"""Filter pipeline table. A filter absent from PIPELINE never runs."""

from .filters import squeeze, wrap

PIPELINE = [
    ("squeeze", squeeze, 10),
    ("wrap", wrap, 20),
]
