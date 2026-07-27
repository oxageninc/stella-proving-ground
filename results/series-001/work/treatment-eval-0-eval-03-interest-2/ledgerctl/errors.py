"""Error hierarchy. `main.py` catches `LedgerError` and nothing else."""


class LedgerError(Exception):
    """Base class for every expected, user-facing ledger failure."""


class ValidationError(LedgerError):
    """A required argument was missing or malformed."""


class UnknownAccount(LedgerError):
    """Named account does not exist in the store."""


class InsufficientFunds(LedgerError):
    """Debit would take an account below zero."""
