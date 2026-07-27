"""The leakage gate. A hit invalidates the epoch — it is not a warning.

Leakage is the failure mode that would quietly invalidate everything: if
evaluation content reaches the persistent store, the treatment arm is being
measured on what it has already been told, and every number above control is
memorization wearing transfer's clothes.

So it is asserted rather than assumed, and the assertion is designed to be
*able to fire*. That is harder than it sounds. Scanning for the bare command
names would drown in false positives — `split`, `merge` and `statement` are
ordinary programming English, and the store is full of ordinary programming
English. Scanning for the task ids would be useless in the other direction:
nothing ever writes `eval-04-split` into a store, so the gate would be green
by construction and prove nothing.

The signature is therefore *derived*: every word n-gram in the evaluation
prompts, minus every n-gram that also occurs in the experience prompts or
anywhere in the corpus the agent legitimately reads. What survives is
vocabulary that can only have come from an evaluation task.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .tasks import CORPUS, load_pool

NGRAM = 4
_WORD = re.compile(r"[a-z0-9_.]+")


def _normalize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _ngrams(text: str, n: int = NGRAM) -> set[str]:
    words = _normalize(text)
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def benign_ngrams() -> set[str]:
    """Vocabulary the agent may legitimately have seen: corpus + experience."""
    benign: set[str] = set()
    for path in sorted(CORPUS.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".md", ".json", ""}:
            try:
                benign |= _ngrams(path.read_text())
            except UnicodeDecodeError:
                continue
    for task in load_pool("experience"):
        benign |= _ngrams(task.prompt)
    return benign


def eval_signature() -> dict[str, set[str]]:
    """Per-eval-task n-grams that occur nowhere the agent is allowed to look."""
    benign = benign_ngrams()
    signature: dict[str, set[str]] = {}
    for task in load_pool("evaluation"):
        unique = _ngrams(task.prompt) - benign
        signature[task.task_id] = unique
    return signature


# --- reading a store as text ----------------------------------------------


def _sqlite_text(path: Path) -> list[tuple[str, str]]:
    """Every text value in every table, tagged with `table.column`."""
    out: list[tuple[str, str]] = []
    if not path.exists():
        return out
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [
            r[0]
            for r in con.execute(
                "select name from sqlite_master where type='table' "
                "and name not like 'sqlite_%'"
            )
        ]
        for table in tables:
            try:
                cur = con.execute(f'select * from "{table}"')
            except sqlite3.DatabaseError:
                continue
            columns = [d[0] for d in cur.description]
            for row in cur.fetchall():
                for column, value in zip(columns, row):
                    if isinstance(value, str) and value:
                        out.append((f"{table}.{column}", value))
                    elif isinstance(value, bytes):
                        try:
                            decoded = value.decode("utf-8")
                        except UnicodeDecodeError:
                            continue
                        if decoded.strip():
                            out.append((f"{table}.{column}", decoded))
    finally:
        con.close()
    return out


def store_text(store: Path) -> list[tuple[str, str]]:
    """All recoverable text from an arm's persistent store."""
    chunks: list[tuple[str, str]] = []
    for name in ("context.db", "store.db"):
        chunks.extend((f"{name}:{loc}", text) for loc, text in _sqlite_text(store / name))
    reflections = store / "reflections.jsonl"
    if reflections.exists():
        for i, line in enumerate(reflections.read_text().splitlines()):
            if line.strip():
                chunks.append((f"reflections.jsonl:{i}", line))
    return chunks


@dataclass
class LeakReport:
    clean: bool
    hits: list[dict]
    scanned_values: int
    signature_size: int

    def summary(self) -> str:
        if self.clean:
            return (
                f"clean — {self.scanned_values} stored values scanned against "
                f"{self.signature_size} evaluation-only n-grams"
            )
        tasks = sorted({h['task_id'] for h in self.hits})
        return f"LEAK — {len(self.hits)} hit(s) for {tasks}"

    def as_dict(self) -> dict:
        return {
            "clean": self.clean,
            "hits": self.hits[:20],
            "hit_count": len(self.hits),
            "scanned_values": self.scanned_values,
            "signature_size": self.signature_size,
        }


def scan(store: Path) -> LeakReport:
    """Scan an arm's store for evaluation vocabulary. A hit invalidates the epoch."""
    signature = eval_signature()
    total_signature = sum(len(v) for v in signature.values())
    values = store_text(store)
    hits: list[dict] = []
    for location, value in values:
        grams = _ngrams(value)
        if not grams:
            continue
        for task_id, task_grams in signature.items():
            overlap = grams & task_grams
            if overlap:
                hits.append(
                    {
                        "task_id": task_id,
                        "location": location,
                        "ngram": sorted(overlap)[0],
                        "excerpt": value[:200],
                    }
                )
    return LeakReport(
        clean=not hits,
        hits=hits,
        scanned_values=len(values),
        signature_size=total_signature,
    )


class EpochInvalidated(RuntimeError):
    """Evaluation content reached the persistent store. The epoch is void."""


def gate(store: Path, arm: str, epoch: int) -> LeakReport:
    report = scan(store)
    if not report.clean:
        detail = json.dumps(report.hits[:5], indent=2)
        raise EpochInvalidated(
            f"epoch {epoch} arm {arm}: evaluation content found in the persistent "
            f"store. This epoch is void and must not be scored.\n{detail}"
        )
    return report
