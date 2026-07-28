"""Shared verifier helpers, mounted read-only into a scoring sandbox.

This file never lives in the agent's workspace while it is working. It is
copied in at scoring time only, alongside the task's own `verify.py`, and the
whole scoring copy is thrown away afterwards. Keeping it out of the workspace
is what stops a handler from being written against the assertions.

Every check here is deterministic: no model, no judge, no fuzzy matching.

## Why checks are named and graded, not a single pass/fail

A trial used to be one bit. Six tasks therefore gave six observations, and the
bootstrap resamples *tasks*, so the experiment's whole resolving power came
from n=6 — a confidence interval wide enough to swallow the effect being
measured. A measured ceiling of +0.133 sat inside a noise band of roughly
±0.20, which is why three separate series returned no stable sign.

Each task already tests four independent house conventions plus its behaviour.
Reporting them separately turns those six bits into ~30 graded observations for
*exactly the same model spend*, and measures the thing context is supposed to
teach directly rather than through the noisy proxy of whole-task success.

Whole-task pass/fail is still reported. It is simply no longer the only signal.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


class VerifyFailure(AssertionError):
    """A verifier assertion failed. Message is recorded verbatim in results."""


class WorkspaceDestroyed(VerifyFailure):
    """The agent removed or corrupted state the task was given.

    Distinguished from a convention failure because it means something very
    different. Two `sweep` trials deleted `ledger.json` outright; the verifier
    reported "ledger file missing", which is true and useless — it named
    neither the convention that broke nor the fact that no convention was
    tested at all. Failures of this kind are noise in the dimension the
    experiment measures, so they get their own label and are counted rather
    than silently averaged in.
    """


#: The four house conventions, in the order `CONTRIBUTING.md` states them.
#: These names are the schema for every result row and for the CI baseline,
#: so they are stable identifiers rather than prose.
CONVENTIONS = ("registered", "minor_units", "ledger_error", "validated")


@dataclass
class CheckReport:
    """Named, independently-scored checks for one task."""

    workspace: Path
    results: list[tuple[str, bool, str]] = field(default_factory=list)

    def check(self, name: str, fn) -> bool:
        """Run one named check, recording pass/fail rather than aborting.

        Independence is the point: an early convention failure must not hide
        the state of the other three, or the finer-grained scoring buys
        nothing.
        """
        try:
            fn()
        except WorkspaceDestroyed as exc:
            self.results.append((name, False, f"workspace-destroyed: {exc}"))
            return False
        except Exception as exc:  # noqa: BLE001 — any failure is a check failure
            self.results.append((name, False, f"{type(exc).__name__}: {exc}"))
            return False
        self.results.append((name, True, ""))
        return True

    @property
    def passed(self) -> bool:
        """The whole task succeeded: every check held."""
        return bool(self.results) and all(ok for _, ok, _ in self.results)

    @property
    def detail(self) -> str:
        return "; ".join(f"{n}: {d}" for n, ok, d in self.results if not ok)[:500]

    def as_dict(self) -> dict[str, bool]:
        return {name: ok for name, ok, _ in self.results}

    @property
    def destroyed_workspace(self) -> bool:
        return any(not ok and "workspace-destroyed" in d for _, ok, d in self.results)


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
        raise WorkspaceDestroyed(f"{db} was removed during the run")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise WorkspaceDestroyed(f"{db} is no longer valid JSON: {exc}") from exc


def write_ledger(workspace: Path, accounts: dict, journal=None, db: str = "ledger.json") -> None:
    """Seed a known ledger state.

    Every verifier calls this **first**, before any assertion. Asserting
    against whatever the agent happened to leave behind conflated "violated a
    convention" with "deleted the file", and reported the second as the first.
    """
    (workspace / db).write_text(
        json.dumps({"accounts": dict(accounts), "journal": list(journal or [])}, indent=2)
    )


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
    try:
        registry = _import(workspace, "ledgerctl.registry")
    except Exception as exc:  # noqa: BLE001
        raise WorkspaceDestroyed(f"ledgerctl.registry no longer imports: {exc}") from exc
    if command not in registry.COMMANDS:
        raise VerifyFailure(
            f"command {command!r} not registered in ledgerctl/registry.py "
            f"COMMANDS (found: {sorted(registry.COMMANDS)})"
        )
    if not hasattr(registry.COMMANDS[command], "run"):
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
        if amount is not None and (isinstance(amount, bool) or not isinstance(amount, int)):
            raise VerifyFailure(
                f"journal[{i}] amount is {type(amount).__name__} "
                f"({amount!r}); amounts must be integer minor units"
            )


def assert_ledger_error(workspace: Path, *argv: str, db: str = "ledger.json") -> str:
    """CONVENTION 3: failures surface as a clean `error:` line, not a traceback."""
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
