# stella-proving-ground

A longitudinal experiment that tries to find out whether Stella's
adaptive-context lifecycle actually makes Stella better — and is built so that
it can return "no effect", and is worth believing precisely because it can.

Not a demo. Not a benchmark score. An experiment with a pre-registered primary
metric, three arms, a held-out pool, and its losses committed alongside its
wins.

## The claim under test

> With the adaptive-context lifecycle enabled, Stella's performance on tasks it
> has never seen improves as a function of experience accumulated on different
> tasks.

Both emphases carry the design. Improvement on tasks the agent has already
worked is memorization, and a context system is *supposed* to memorize —
measuring it proves nothing. The only claim worth making is **transfer**, and
transfer is only observable on a held-out set.

## Why it lives outside Stella

A proving ground inside Stella's own CI acquires, structurally, an interest in
the number going up; eventually someone tunes the eval instead of the agent.
Separate repo, separate cadence, raw results published with the losses
included.

It also wants a different release rhythm: the harness re-scores old series from
raw data when the methodology changes (`proving-ground scoreboard`), which is
awkward inside the repo being scored.

## What it does not rebuild

The harness contributes **no task-running or verification logic of its own**
beyond invoking the Stella binary the way any caller would. It is the
longitudinal layer: epochs, arms, held-out splits, a leakage gate, statistics,
and a scoreboard.

## Design

### Two pools, never mixed

- **Experience pool** — tasks the agent works on. The lifecycle learns from
  these freely.
- **Evaluation pool** — held out. Measured, never learned from. Every
  evaluation trial runs against a *copy* of the arm's context store and its
  writes are discarded, so measuring cannot itself become experience.

### Epochs

```
E0: evaluate (cold — no experience)
    → work a block of experience tasks
E1: evaluate
    → work another block
E2: evaluate …
```

The series is the result. A single epoch pair proves nothing.

### Three arms, because two is not enough

| Arm | Store at evaluation | Isolates |
|---|---|---|
| **treatment** | persists, grown on the experience pool | the real system |
| **control** | empty before every evaluation | improvement that is not from memory at all |
| **sham** | persists, grown on a *different* task family | context volume vs. the **right** context |

Without the sham arm, "more tokens in the prompt helped" is indistinguishable
from "learned knowledge helped", and only the second is self-improvement.

### The tasks

A synthetic Python CLI (`tasks/corpus/ledgerctl`) with four house conventions
that are documented in `CONTRIBUTING.md`, enforced by the verifiers, and easy to
miss: handlers must be registered in `registry.py`; money is integer minor units
and never floats; failures must raise a `LedgerError` subclass; arguments go
through `validate.require`.

Every task is the same shape — add one command — so the pools differ only in
*which* command, never in difficulty or form. That matters: if evaluation tasks
were systematically harder, an accuracy gap between arms could be a difficulty
artifact rather than a transfer effect.

The conventions are the transferable knowledge. They are discoverable by
reading the repository and expensive to rediscover every time, which is exactly
the situation in which accumulated context should pay for itself.

### The leakage gate

Leakage is the failure mode that would quietly invalidate everything, so it is
asserted rather than assumed. After every epoch the persistent store is scanned
for evaluation vocabulary; **a hit invalidates the epoch**, it does not warn.

The signature is derived rather than hand-written: every word 4-gram in the
evaluation prompts, minus every 4-gram occurring in the experience prompts or
anywhere in the corpus the agent legitimately reads. Scanning for bare command
names would drown in false positives (`split`, `merge` and `statement` are
ordinary programming English); scanning for task ids would be green by
construction and prove nothing.

Controlled in both directions: clean against a store full of legitimate
experience content, and firing on a leaked prompt *and* on a single distinctive
output string dropped into an otherwise clean store.

### Verifiers

Deterministic only — tests pass, exact output, exact state. Never an LLM judge:
a judge rewards confident prose, which is precisely what a degenerate agent
optimizes toward.

The agent cannot reach them. Verifiers live outside the workspace and are
copied into a throwaway scoring sandbox after the agent has stopped.

Both halves of the control are enforced by `tests/test_verifiers.py`:

- **negative** — all 16 tasks fail against an untouched corpus, so a verifier
  cannot pass for free;
- **positive** — all 16 pass against a reference implementation, so a verifier
  cannot be unsatisfiable. An unsatisfiable verifier scores every arm at zero
  and looks exactly like a null result.

### Everything else pinned

Model, reflection model, provider, reasoning posture, per-trial budget, the
Stella commit and binary hash, and a digest of the task pool are recorded on
every result row. `assert_series_compatible` **refuses to append** to a series
whose pinned configuration differs, rather than silently producing a chart where
the improvement is really a model upgrade.

## Results

- `PREREGISTRATION.md` — metrics, effect size and falsification conditions,
  committed before the first trial ran.
- `FINDINGS.md` — defects found while building the harness. Several of them
  make the lifecycle appear to run while producing nothing, and two of them
  contradict premises of the issue this repo was built for.
- `results/series-001/` — raw append-only `results.jsonl`, per-epoch
  `epochs.jsonl`, and the generated `SCOREBOARD.md`.

## Usage

```bash
# run a series
python3 -m proving_ground.cli run --root results/series-002 \
    --epochs 5 -k 5 --block-size 5 --concurrency 6

# re-score an existing series from raw data, no model calls
python3 -m proving_ground.cli scoreboard --root results/series-001

# scan any context store for evaluation leakage
python3 -m proving_ground.cli scan path/to/.stella/private

# both halves of the verifier control
python3 -m pytest tests/ -q
```

## Honest limitations

- **Tasks are synthetic.** The corpus is purpose-built, so it is not affected by
  pretraining contamination the way SWE-bench or Terminal-Bench are — but it is
  also narrower than real repository work, and a result here is evidence about
  this task family rather than about software engineering.
- **One model family, one budget.** A series is pinned; nothing here shows the
  effect direction generalizes across model tiers.
- **Only half the lifecycle is live.** Attribution and retirement are not on
  Stella's `main` (see `FINDINGS.md` §6), so the regression-rate metric has no
  retirement to catch yet. It is reported anyway, so the baseline exists before
  retirement lands.
- **The proposal pump is an intervention.** Left alone, nothing extracts
  reflection lessons on the `stella run` path. Enabling the pump measures the
  lifecycle as designed rather than as currently plumbed, and the pinned config
  records which was measured.
