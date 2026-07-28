# Superseded — do not compare against current results

These trials (and the sibling `results/diluted-probe/`) ran on task-pool digest
`c6cbc5947ce18680`: 6 evaluation tasks, one bit of outcome per task, no seeding
before stateful assertions.

The pool has since been rebuilt — 12 evaluation tasks, ~5 named checks each,
seeded before asserting — and is now `f8a7dfe75caf484c`. Comparing across that
boundary measures the instrument change, not the treatment.

They were also scored against a **pooled cold control from series-001/-002**
rather than a control arm run alongside them, which compounds the same problem:
the baseline came from a different pool *and* a different run.

Kept because they were paid for and because the arms are legible from the rows
themselves, not because they say anything about the current question. They are
replaced by `results/precision-probe/`, which runs control, oracle and diluted
interleaved in one invocation so all three share a digest by construction.

See `experiments/precision_probe.py`, and finding 10 in `FINDINGS.md`.
