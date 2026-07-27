"""Shared verifier helpers, mounted read-only into a scoring sandbox.

This file never lives in the agent's workspace while it is working. It is
copied in at scoring time only, alongside the task's own `verify.py`, and the
whole scoring copy is thrown away afterwards. Keeping it out of the workspace
is what stops a handler from being written against the assertions.

Every check here is deterministic: no model, no judge, no fuzzy matching.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path


class VerifyFailure(AssertionError):
    """A verifier assertion failed. Message is recorded verbatim in results."""


def run_cli(workspace: Path, *argv: str, db: str = "ledger.json"):
    """Invoke the ledgerctl CLI in `workspace`. Returns (rc, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, "-m", "ledgerctl.main", *argv, "--db", db],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def load_ledger(workspace: Path, db: str = "ledger.json") -> dict:
    path = workspace / db
    if not path.exists():
        raise VerifyFailure(f"ledger file {db} missing after run")
    return json.loads(path.read_text())


def _import(workspace: Path, module: str):
    """Import a module out of the candidate workspace, fresh each time."""
    ws = str(workspace)
    if ws not in sys.path:
        sys.path.insert(0, ws)
    for name in list(sys.modules):
        if name == "ledgerctl" or name.startswith("ledgerctl."):
            del sys.modules[name]
    return importlib.import_module(module)


# --- convention checks: the transferable knowledge -------------------------


def assert_registered(workspace: Path, command: str) -> None:
    """CONVENTION 1: the handler is wired into registry.COMMANDS."""
    registry = _import(workspace, "ledgerctl.registry")
    if command not in registry.COMMANDS:
        raise VerifyFailure(
            f"command {command!r} not registered in ledgerctl/registry.py "
            f"COMMANDS (found: {sorted(registry.COMMANDS)})"
        )
    handler = registry.COMMANDS[command]
    if not hasattr(handler, "run"):
        raise VerifyFailure(f"registered handler for {command!r} exposes no run()")


def assert_minor_units(workspace: Path, db: str = "ledger.json") -> None:
    """CONVENTION 2: every persisted amount is an integer, never a float."""
    data = load_ledger(workspace, db)
    for account, value in data.get("accounts", {}).items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise VerifyFailure(
                f"balance for {account!r} is {type(value).__name__} "
                f"({value!r}); balances must be integer minor units"
            )
    for i, entry in enumerate(data.get("journal", [])):
        amount = entry.get("amount")
        if amount is not None and (
            isinstance(amount, bool) or not isinstance(amount, int)
        ):
            raise VerifyFailure(
                f"journal[{i}] amount is {type(amount).__name__} "
                f"({amount!r}); amounts must be integer minor units"
            )


def assert_ledger_error(workspace: Path, *argv: str, db: str = "ledger.json") -> str:
    """CONVENTION 3: failures surface as a clean `error:` line, not a traceback.

    An exception that is not a LedgerError subclass escapes main() and prints a
    traceback, which is exactly what this catches.
    """
    rc, out, err = run_cli(workspace, *argv, db=db)
    if "Traceback" in err:
        tail = err.strip().splitlines()[-1] if err.strip() else ""
        raise VerifyFailure(
            f"uncaught exception for {' '.join(argv)!r}: {tail} — handlers must "
            f"raise a LedgerError subclass from ledgerctl/errors.py"
        )
    if rc == 0:
        raise VerifyFailure(f"expected failure exit for {' '.join(argv)!r}, got rc=0")
    if not err.startswith("error:"):
        raise VerifyFailure(
            f"expected an 'error: ...' line for {' '.join(argv)!r}, got {err!r}"
        )
    return err


def assert_validates(workspace: Path, command: str, *present: str, db: str = "ledger.json") -> None:
    """CONVENTION 4: missing arguments are reported by name via validate.require."""
    err = assert_ledger_error(workspace, command, *present, db=db)
    if "missing required argument" not in err:
        raise VerifyFailure(
            f"{command!r} with missing arguments produced {err!r}; handlers must "
            f"call validate.require(...) so the missing field is named"
        )


def write_ledger(workspace: Path, accounts: dict, journal=None, db: str = "ledger.json") -> None:
    (workspace / db).write_text(
        json.dumps({"accounts": dict(accounts), "journal": list(journal or [])}, indent=2)
    )
