# Contributing to ledgerctl

House rules. These are enforced by review and by the test suite.

## Adding a command

1. Create `ledgerctl/commands/<name>.py` exposing exactly one entry point:

   ```python
   def run(args: dict, store: Store) -> str:
       ...
   ```

   It returns the single line the CLI prints. It must not print anything itself.

2. **Register it.** Add the module to `COMMANDS` in `ledgerctl/registry.py`.
   An unregistered handler is dead code — `main.py` dispatches only through
   the registry and will report `unknown command`.

## Money

All monetary values are handled internally as **integer minor units** (cents).
Floats are banned in ledger arithmetic: they lose pennies under repeated
addition and the reconciliation suite will catch it.

- Parse user input with `money.parse_amount("12.50") -> 1250`.
- Render with `money.format_amount(1250) -> "12.50"`.

Balances, postings, and every amount stored in `Store` are `int`.

## Errors

Raise a subclass of `LedgerError` from `ledgerctl/errors.py`. `main.py`
catches `LedgerError` and turns it into a clean `error: ...` line with exit
code 1; every other exception escapes as a traceback and is a bug.

Use the specific subclass — `UnknownAccount`, `InsufficientFunds`,
`ValidationError` — not bare `LedgerError`.

## Validation

Handlers do not index `args` directly. Call
`validate.require(args, "from", "to", "amount")` first; it raises
`ValidationError` naming the missing field.
