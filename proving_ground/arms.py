"""The three arms.

Two arms are not enough. With treatment and control alone, "the prompt got
bigger and that helped" is indistinguishable from "the agent knew something
useful", and only the second is self-improvement. The sham arm separates them.

| arm       | store at evaluation                          | isolates                       |
|-----------|----------------------------------------------|--------------------------------|
| treatment | persists, grown on the experience pool       | the real system                |
| control   | empty, every epoch                           | improvement that is not memory |
| sham      | persists, grown on a *different* task family | context volume vs. content     |

The sham store is built by doing real work on a foreign corpus (`textkit`, a
text-processing CLI with deliberately different house conventions). Its
memories are therefore genuine, plausible and wrong — which is exactly the
control that matters. Populating it with noise instead would test nothing: no
agent is fooled by noise, and being unfooled by noise is not evidence.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .tasks import REPO, Task, load_pool

FOREIGN_CORPUS = REPO / "tasks" / "foreign" / "textkit"


@dataclass(frozen=True)
class Arm:
    name: str
    #: corpus the experience block is worked against
    experience_corpus: Path
    #: whether evaluation trials are seeded with this arm's store
    seeded_evaluation: bool
    #: whether the arm accumulates a store at all
    accumulates: bool
    description: str

    def store(self, root: Path) -> Path:
        return root / "stores" / self.name

    def experience_pool(self) -> list[Task]:
        if self.name == "sham":
            return load_pool("sham")
        if self.name == "control":
            return []
        return load_pool("experience")


TREATMENT = Arm(
    name="treatment",
    experience_corpus=REPO / "tasks" / "corpus" / "ledgerctl",
    seeded_evaluation=True,
    accumulates=True,
    description="lifecycle on; store persists across epochs, grown on the experience pool",
)

CONTROL = Arm(
    name="control",
    experience_corpus=REPO / "tasks" / "corpus" / "ledgerctl",
    seeded_evaluation=False,
    accumulates=False,
    description="store empty before every evaluation; measures run-to-run variance and drift",
)

SHAM = Arm(
    name="sham",
    experience_corpus=FOREIGN_CORPUS,
    seeded_evaluation=True,
    accumulates=True,
    description="store persists but is grown on a different task family; measures context volume vs. content",
)

ARMS = {a.name: a for a in (TREATMENT, CONTROL, SHAM)}


def reset_store(arm: Arm, root: Path) -> None:
    store = arm.store(root)
    if store.exists():
        shutil.rmtree(store)
    store.mkdir(parents=True, exist_ok=True)


def store_stats(store: Path) -> dict:
    """How much the arm has actually accumulated, for the volume comparison.

    Reported per epoch so a reader can check the sham arm really is
    volume-matched — a sham arm carrying a tenth of treatment's memories would
    be no control at all.
    """
    import sqlite3

    stats = {"memories": 0, "episodes": 0, "context_records": 0, "bytes": 0}
    db = store / "context.db"
    if not db.exists():
        return stats
    stats["bytes"] = sum(f.stat().st_size for f in store.glob("*") if f.is_file())
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for table, key in (
            ("memory", "memories"),
            ("episode", "episodes"),
            ("context_records", "context_records"),
        ):
            try:
                stats[key] = con.execute(f"select count(*) from {table}").fetchone()[0]
            except sqlite3.DatabaseError:
                pass
    finally:
        con.close()
    return stats
