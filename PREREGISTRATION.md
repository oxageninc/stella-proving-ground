# Pre-registration — series 001

Every value below was committed in code (`proving_ground/stats.py`,
`proving_ground/config.py`) in commit `362593f`, **before** the first trial of
series 001 ran. That commit is the timestamp; this file is the readable form of
it, not a later reconstruction.

## The claim under test

> With the adaptive-context lifecycle enabled, Stella's performance on tasks it
> has never seen improves as a function of experience accumulated on different
> tasks.

Both emphases are load-bearing. Improvement on tasks already worked is
memorization, and a context system is *supposed* to memorize — measuring it
proves nothing. The claim is about **transfer**, so it is only ever measured on
a held-out pool.

## Primary metric

**Resolution accuracy** — the fraction of held-out evaluation tasks whose
deterministic verifier passes.

Aggregated as the mean per-task pass rate, with the **task** as the unit of
replication. *k* trials of one task are not *k* independent observations of the
pool, so the bootstrap resamples tasks, not trials.

## Secondary metrics

| Metric | Definition |
|---|---|
| Token efficiency | total tokens ÷ solved task |
| Cost | USD ÷ solved task |
| Speed | wall-clock seconds and model calls ÷ solved task |
| Context efficiency | recalled-context tokens per model call; share of recalled frames subsequently cited |
| **Regression rate** | tasks solved at epoch *N* that fail at *N+1* |

Regression rate is the one usually left out and the one that catches the
interesting failure: a system that learns net-positive while silently breaking
things it used to get right.

## Effect size that counts as a result

`MIN_MEANINGFUL_EFFECT = 0.10` — a **10 percentage-point** absolute difference
in resolution accuracy, paired per task, with a 95% bootstrap CI excluding
zero.

A point estimate that clears 10 points but whose CI spans zero is reported as
**no detectable difference**. A difference that is statistically separated but
smaller than 10 points is reported as **below threshold**. Neither is a result.

## Statistics

- *k* = 5 independent trials per task, per arm, per epoch.
- Percentile bootstrap, `BOOTSTRAP_DRAWS = 10000`, `BOOTSTRAP_SEED = 20260726`.
  Seeded so any published number reproduces exactly.
- **Paired** per-task comparison between arms at the same epoch. Pairing on
  task has far more power than comparing pool means and removes task-difficulty
  drift from the contrast.

## Arms

| Arm | Store at evaluation | Isolates |
|---|---|---|
| treatment | persists, grown on the experience pool | the real system |
| control | empty before every evaluation | improvement that is not from memory at all |
| sham | persists, grown on a *different* task family | context volume vs. the *right* context |

The sham arm is the one most benchmarks skip and the one that makes the result
defensible. Without it, "more tokens in the prompt helped" is indistinguishable
from "learned knowledge helped", and only the second is self-improvement.

Sham memories are produced by doing real work on a foreign corpus (`textkit`, a
text-processing CLI with deliberately different house conventions), not by
generating noise. No agent is fooled by noise, and being unfooled by noise is
not evidence.

## What would falsify the claim

Stated up front, so the experiment is honest:

- Treatment tracks control within confidence intervals across the series → the
  lifecycle does not transfer.
- Treatment tracks **sham** → context volume helps, learned content does not.
  This is the most likely null result and the most useful one.
- Accuracy rises while regression rate rises with it → net movement is churn,
  not learning.
- Improvement appears only on repeat tasks and not on fresh ones →
  memorization, correctly named.

Any of those is a publishable result and will be published.

## Anti-gaming commitments

- **Deterministic verifiers only.** Tests pass or they do not. Never an LLM
  judge — a judge rewards confident prose, which is what a degenerate agent
  optimizes toward.
- **The agent cannot reach the harness.** Verifiers live outside the workspace
  and are copied into a throwaway scoring sandbox only after the agent has
  stopped.
- **Evaluation writes are discarded.** Every evaluation trial gets its own copy
  of the arm's store and never writes back, so measuring cannot become
  experience.
- **The leakage gate is a hard gate.** After every epoch the store is scanned
  for evaluation-only vocabulary; a hit invalidates the epoch rather than
  raising a warning.
- **Publish losses.** Raw results are committed whatever they say.

## Amendment 1 — leakage-gate definition (recorded after E2 of the first attempt)

The first attempt at series 001 was **aborted by its own leakage gate at epoch
2**, and the hit was a false positive. This section records the change and why
it is not a result being laundered.

The gate flagged the 4-gram `"from bob to alice"` in a stored tool call. Every
word in it — `from`, `to`, and both account names — is shared vocabulary
present in the corpus and in every task. It reached the store because an agent
working the **rename** experience task improvised
`rename --from bob --to alice`, while `eval-06-merge`'s prompt happens to read
`merge --from bob --to alice`. No evaluation content was involved.

The signature derivation now additionally requires an n-gram to contain at
least one word that is itself absent from the benign vocabulary — a genuinely
evaluation-only word such as `refunded`, `swept`, `merged` or `credited`.

Three things keep this honest:

1. **The justification is mechanical, not statistical.** The hit was traced to
   a specific experience task producing the sequence; it was not reclassified
   because the epoch was inconvenient.
2. **The gate is still controlled, and the controls are unchanged.** It still
   fires on a leaked prompt and on a single distinctive output line
   (`test_gate_fires_on_a_single_distinctive_string`). The signature shrank
   from 243 to 207 n-grams; it was not gutted.
3. **The affected series was discarded and re-run from scratch**, not
   re-scored under the new rule. No trial that ran under the old gate
   contributes to any published number.

The general point is worth stating, because a hard gate has two failure modes
and only one of them is obvious: a gate that misses leakage invalidates the
result silently, and a gate that cries wolf gets switched off by whoever is
tired of re-running. Both are fatal; the second is the one that looks
responsible right up until someone disables it.

## Pinned configuration

A change to any of these forks a new series; `assert_series_compatible` raises
rather than appending. Recorded per result row.

| Field | Value |
|---|---|
| worker model | `z-ai/glm-4.7-flash` |
| reflection model | `google/gemini-2.5-flash-lite` |
| provider | `openrouter` |
| reasoning | `off` |
| per-trial budget | `$0.25` |
| lifecycle | enabled |
| proposal pump | enabled (see below) |

Two of these need justifying, because both are consequences of defects found
while building the harness (`FINDINGS.md`).

**The reflection model is pinned separately from the worker model.** Reflection
runs on `default_model`, and it must emit a bare JSON array. `glm-4.7-flash`
emits chain-of-thought prose instead and parses to zero lessons, which starves
the entire lifecycle. It is a competent worker and a useless reflector, so the
two roles are pinned to different models.

**The proposal pump is enabled.** On the `stella run` path, reflection lessons
are never extracted into `context_records` by anything. Without an explicit
`stella proposals refresh`, the treatment arm would carry no durable content and
the experiment would measure plumbing rather than transfer. The pump is an
intervention and is recorded as part of the pinned config, so a reader can tell
this series apart from an unassisted one.
