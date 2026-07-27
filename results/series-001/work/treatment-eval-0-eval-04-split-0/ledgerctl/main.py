"""CLI entry point. Dispatches through the registry; catches LedgerError only."""

import sys

from .errors import LedgerError
from .registry import COMMANDS
from .store import Store

DEFAULT_DB = "ledger.json"


def parse_argv(argv: list[str]) -> tuple[str, dict]:
    if not argv:
        raise LedgerError("usage: ledgerctl <command> [--key value ...]")
    command, rest = argv[0], argv[1:]
    args: dict = {}
    i = 0
    while i < len(rest):
        token = rest[i]
        if not token.startswith("--"):
            raise LedgerError(f"unexpected token: {token}")
        key = token[2:]
        if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
            args[key] = rest[i + 1]
            i += 2
        else:
            args[key] = True
            i += 1
    return command, args


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        command, args = parse_argv(argv)
        handler = COMMANDS.get(command)
        if handler is None:
            raise LedgerError(f"unknown command: {command}")
        db = args.pop("db", DEFAULT_DB)
        store = Store.load(db)
        line = handler.run(args, store)
        store.save(db)
        print(line)
        return 0
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
