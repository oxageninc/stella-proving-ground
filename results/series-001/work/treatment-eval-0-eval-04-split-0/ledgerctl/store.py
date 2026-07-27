"""In-memory account store loaded from / saved to a JSON file.

Every balance is an integer minor unit. See CONTRIBUTING.md.
"""

import json
from pathlib import Path

from .errors import InsufficientFunds, UnknownAccount


class Store:
    def __init__(self, accounts: dict[str, int] | None = None):
        self.accounts: dict[str, int] = dict(accounts or {})
        self.journal: list[dict] = []

    @classmethod
    def load(cls, path: str | Path) -> "Store":
        p = Path(path)
        if not p.exists():
            return cls()
        raw = json.loads(p.read_text())
        s = cls(raw.get("accounts", {}))
        s.journal = raw.get("journal", [])
        return s

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps({"accounts": self.accounts, "journal": self.journal}, indent=2)
        )

    def balance(self, account: str) -> int:
        if account not in self.accounts:
            raise UnknownAccount(f"no such account: {account}")
        return self.accounts[account]

    def credit(self, account: str, minor: int) -> None:
        if account not in self.accounts:
            raise UnknownAccount(f"no such account: {account}")
        self.accounts[account] += minor

    def debit(self, account: str, minor: int) -> None:
        if account not in self.accounts:
            raise UnknownAccount(f"no such account: {account}")
        if self.accounts[account] < minor:
            raise InsufficientFunds(
                f"{account} has insufficient funds for this debit"
            )
        self.accounts[account] -= minor

    def post(self, entry: dict) -> None:
        """Append a journal entry. Amounts in entries are integer minor units."""
        self.journal.append(entry)
