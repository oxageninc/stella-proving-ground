"""Pinned run configuration, and the guard that refuses to mix series.

Everything that could move a number and is not the thing under test gets
recorded on every result row: model, provider, reasoning posture, the Stella
commit, the binary hash, the task-pool digest, the harness commit.

The guard exists because of a specific, easy, invisible mistake — appending
epochs to a series after upgrading the model, and reading the resulting rise as
learning. `assert_series_compatible` makes that an error rather than a chart.

There is a second, subtler version of the same mistake that this module also
defends against. Stella resolves its worker model from
`~/.stella/settings.json` (`agent_engine_config.pipeline_worker_model`), and
that setting **outranks the `--model` flag** on the pipeline path — while the
JSON envelope still reports the model that was *asked for*. A harness trusting
`--model` plus the envelope would pin nothing at all. So the pinned model is
written into a workspace-local `.stella/settings.json`, and `observed_models`
reads back what actually ran from per-call `step_usage` events.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pool_digest() -> str:
    """Hash every task file. A changed task invalidates comparison too."""
    h = hashlib.sha256()
    for pool in ("experience", "evaluation"):
        for path in sorted((REPO / "tasks" / pool).rglob("*")):
            if path.is_file():
                h.update(str(path.relative_to(REPO)).encode())
                h.update(path.read_bytes())
    h.update((REPO / "tasks" / "verifier_lib.py").read_bytes())
    return h.hexdigest()[:16]


DEFAULT_BINARY = Path.home() / "Projects" / "stella" / "target" / "release" / "stella"


@dataclass(frozen=True)
class PinnedConfig:
    """The immutable identity of a series. Any change forks a new series."""

    model: str = "z-ai/glm-4.7-flash"
    #: Reflection runs on `default_model`, not on the worker model — there is no
    #: `reflection` agent kind to point at. It is pinned separately because the
    #: two roles have genuinely different requirements: the worker has to write
    #: working code, while reflection has to emit a bare JSON array. A model can
    #: be good at the first and hopeless at the second, and when it is, the
    #: lifecycle silently receives nothing at all. See FINDINGS.md.
    reflection_model: str = "google/gemini-2.5-flash-lite"
    provider: str = "openrouter"
    reasoning: str = "off"
    budget_usd: float = 0.25
    #: Extract observations from the reflection log after each experience block.
    #: Without this nothing is ever extracted on the `stella run` path, so the
    #: lifecycle cannot advance past reflection. Recorded as part of the pinned
    #: config because it is an intervention, not a default.
    pump_proposals: bool = True
    stella_binary: str = str(DEFAULT_BINARY)
    stella_commit: str = ""
    stella_version: str = ""
    binary_sha256: str = ""
    harness_commit: str = ""
    task_pool_digest: str = ""
    lifecycle_enabled: bool = True

    @classmethod
    def resolve(cls, **overrides) -> "PinnedConfig":
        binary = Path(overrides.pop("stella_binary", str(DEFAULT_BINARY)))
        stella_repo = binary.parent.parent.parent
        version = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True
        ).stdout.strip()
        return cls(
            stella_binary=str(binary),
            stella_commit=_git(stella_repo, "rev-parse", "HEAD"),
            stella_version=version,
            binary_sha256=_sha256_file(binary),
            harness_commit=_git(REPO, "rev-parse", "HEAD"),
            task_pool_digest=pool_digest(),
            **overrides,
        )

    def as_dict(self) -> dict:
        return asdict(self)

    def fingerprint(self) -> str:
        """Everything that must match for two epochs to belong to one series."""
        keys = (
            "model",
            "reflection_model",
            "pump_proposals",
            "provider",
            "reasoning",
            "budget_usd",
            "stella_commit",
            "binary_sha256",
            "task_pool_digest",
            "lifecycle_enabled",
        )
        payload = json.dumps({k: getattr(self, k) for k in keys}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class SeriesConflict(RuntimeError):
    """Refusing to append an epoch whose pinned config differs from the series."""


def assert_series_compatible(results_path: Path, config: PinnedConfig) -> None:
    """Refuse to append to a series pinned to a different configuration.

    A model upgrade mid-series produces exactly the shape everyone wants to see
    — a line going up — for exactly the wrong reason. This makes it a crash.
    """
    if not results_path.exists():
        return
    want = config.fingerprint()
    with results_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            got = row.get("config_fingerprint")
            if got and got != want:
                raise SeriesConflict(
                    f"{results_path.name} is pinned to config {got}; this run is "
                    f"{want}. A pinned-config change invalidates the series — "
                    f"start a new series rather than appending.\n"
                    f"  existing: {json.dumps(row.get('config', {}), sort_keys=True)}\n"
                    f"  this run: {json.dumps(config.as_dict(), sort_keys=True)}"
                )
            return  # the series is homogeneous by construction; one row suffices


def workspace_settings(config: PinnedConfig) -> dict:
    """The `.stella/settings.json` written into every workspace.

    This is the only reliable way to pin the model: `--model` loses to the
    user's global `pipeline_worker_model` on the pipeline path.
    """
    agent = {"provider": config.provider, "reasoning": config.reasoning}
    return {
        "agent_engine_config": {
            "auto_mode": "off",
            "effort_auto": "off",
            "reasoning_auto": "off",
            "default_model": config.reflection_model,
            "pipeline_worker_model": config.model,
            "pipeline_triage_model": config.model,
            "pipeline_judge_model": config.model,
            "agents": {
                "default": dict(agent),
                "worker": dict(agent),
                "triage": dict(agent),
                "judge": dict(agent),
            },
        },
        "context": {"lifecycle": {"enabled": config.lifecycle_enabled}},
    }


def observed_models(events: list[dict]) -> list[str]:
    """Which models actually ran, read from per-call metering events.

    Deliberately not the envelope's `model` field — that reports the request.
    """
    return sorted(
        {e["model"] for e in events if e.get("type") == "step_usage" and e.get("model")}
    )


def env_for_run(config: PinnedConfig) -> dict:
    """Process environment for a trial.

    Reflection stays enabled on purpose: `STELLA_DISABLE_REFLECTION=1` would
    stop observations being mined, and observations are the input to the very
    lifecycle under test.
    """
    env = os.environ.copy()
    env["STELLA_BUDGET"] = str(config.budget_usd)
    env["STELLA_CATALOG_AUTO_REFRESH"] = "0"
    env["NO_COLOR"] = "1"
    env.pop("STELLA_MODEL", None)
    env.pop("STELLA_DISABLE_REFLECTION", None)
    return env
