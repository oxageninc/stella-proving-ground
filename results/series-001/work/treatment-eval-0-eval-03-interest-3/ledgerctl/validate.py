"""Argument validation. Handlers call `require` before touching `args`."""

from .errors import ValidationError


def require(args: dict, *fields: str) -> None:
    """Raise ValidationError naming the first missing or empty field."""
    for field in fields:
        if field not in args or args[field] in (None, ""):
            raise ValidationError(f"missing required argument: --{field}")
