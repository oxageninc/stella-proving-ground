"""The cashflow report."""

from ..money import format_amount


def render(store, **opts) -> str:
    rows = []
    for name in sorted(store.accounts):
        rows.append(f"{name} {format_amount(store.balance(name))}")
    return "\n".join(rows)
