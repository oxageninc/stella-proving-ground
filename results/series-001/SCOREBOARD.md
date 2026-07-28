# Scoreboard

Series pinned to `z-ai/glm-4.7-flash` via `openrouter`, Stella `stella 0.5.54` (`4e1f7d8d39c7`), task pool `c6cbc5947ce18680`.

Evaluation pool is held out: it is measured and never learned from. Primary metric is resolution accuracy against a deterministic verifier. Pre-registered threshold for a result: **10%** absolute, paired, CI excluding zero.


## Verdict

**The claim is supported — PRELIMINARY ONLY.** treatment exceeds both control and sham by more than the pre-registered threshold, with CIs excluding zero; but this is 2 epochs — a single pair — and the pre-registration commits to the series being the result. Directional evidence, not a finding.

At the final epoch (E1), treatment − control = +0.300 (95% CI [+0.067, +0.533]); treatment − sham = +0.342 (95% CI [+0.083, +0.583]).

Treatment moved +0.300 across the series against a control arm that drifted 0.067 on its own — treatment clears control's own run-to-run movement. Treatment regression rate: 0.000 (0 task-epochs lost).


**Empirical null.** The control arm does no experience work and is wiped before every evaluation, so its 2 epochs are the same experiment repeated. It ranged 0.067 (sd 0.047) across them, with nothing changed. Any effect smaller than that band is not distinguishable from nothing.

## Resolution accuracy (primary)

Mean per-task pass rate, with a 95% bootstrap CI over tasks.

| arm | E0 | E1 |
|---|---|---|
| **control** | 0.567 [0.333, 0.733] | 0.500 [0.233, 0.733] |
| **sham** | 0.567 [0.300, 0.800] | 0.458 [0.200, 0.725] |
| **treatment** | 0.500 [0.233, 0.767] | 0.800 [0.667, 0.933] |

## Store growth

Memories carried into each epoch's evaluation. The sham arm must stay comparable to treatment or it is no control at all.

| arm | E0 | E1 |
|---|---|---|
| control | 0 | 0 |
| sham | 0 | 6 |
| treatment | 0 | 12 |

## Token efficiency — tokens per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 1472099 | 2146693 |
| sham | 1679254 | 3585140 |
| treatment | 2287980 | 1719448 |

## Cost — USD per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 0.0855 | 0.0396 |
| sham | 0.0317 | 0.0467 |
| treatment | 0.0432 | 0.0221 |

## Speed — seconds per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 308.7 | 308.1 |
| sham | 264.0 | 356.4 |
| treatment | 265.6 | 210.7 |

## Speed — model calls per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 91.12 | 117.73 |
| sham | 94.41 | 182.08 |
| treatment | 128.53 | 91.38 |

## Context efficiency — recalled tokens per model call

| arm | E0 | E1 |
|---|---|---|
| control | 0.6 | 0.5 |
| sham | 0.6 | 7.7 |
| treatment | 0.5 | 8.9 |

## Context efficiency — share of recalled frames cited

| arm | E0 | E1 |
|---|---|---|
| control | 0.000 | 0.000 |
| sham | 0.000 | 0.000 |
| treatment | 0.000 | 0.000 |

## Memorization check — worked tasks vs. held-out tasks

The evaluation pool is never worked, so it can only show transfer. The experience pool *is* worked, so it can show memorization. Improvement that appears on worked tasks and not on held-out ones is memorization, correctly named — and a context system is supposed to memorize, so seeing it here is expected rather than damning. The divergence between the two columns is the measurement.

| arm | epoch | worked-task pass rate | held-out pass rate | divergence |
|---|---|---|---|---|
| control | E0 | — (n=0) | 0.567 (n=30) | — |
| control | E1 | — (n=0) | 0.500 (n=30) | — |
| sham | E0 | — (n=0) | 0.567 (n=30) | — |
| sham | E1 | — (n=0) | 0.448 (n=29) | — |
| treatment | E0 | 0.600 (n=5) | 0.500 (n=30) | +0.100 |
| treatment | E1 | — (n=0) | 0.800 (n=30) | — |

## Instrument health

Degenerate trials — ones that produced no work at all — are reported separately, because they fail identically to an agent that tried and got it wrong. A null result caused by aborted runs is not a null result about the lifecycle.

| arm | epoch | trials | zero-work | non-completed status | mean calls |
|---|---|---|---|---|---|
| control | E0 | 30 | 0 | 13 | 51.6 |
| control | E1 | 30 | 0 | 11 | 58.9 |
| sham | E0 | 30 | 0 | 12 | 53.5 |
| sham | E1 | 29 | 0 | 13 | 81.6 |
| treatment | E0 | 30 | 0 | 17 | 64.3 |
| treatment | E1 | 30 | 1 | 9 | 73.1 |

## Regression rate

Tasks solved at epoch *N* that fail at *N+1*. A system can learn net-positive while silently breaking what it used to get right.

| arm | transition | solved before | regressed | rate | tasks |
|---|---|---|---|---|---|
| control | E0→E1 | 5 | 2 | 0.400 | eval-01-refund, eval-06-merge |
| sham | E0→E1 | 4 | 2 | 0.500 | eval-04-split, eval-05-statement |
| treatment | E0→E1 | 3 | 0 | 0.000 | — |

## Paired comparisons

Same task, same epoch, arm minus arm. Pairing on task has far more power than comparing pool means.

| epoch | comparison | delta | 95% CI | verdict |
|---|---|---|---|---|
| E0 | treatment − control | -0.067 | [-0.300, +0.167] | no detectable difference (CI spans zero) |
| E0 | treatment − sham | -0.067 | [-0.233, +0.133] | no detectable difference (CI spans zero) |
| E0 | sham − control | +0.000 | [-0.133, +0.133] | no detectable difference (CI spans zero) |
| E1 | treatment − control | +0.300 | [+0.067, +0.533] | difference exceeds the pre-registered threshold |
| E1 | treatment − sham | +0.342 | [+0.083, +0.583] | difference exceeds the pre-registered threshold |
| E1 | sham − control | -0.042 | [-0.333, +0.250] | no detectable difference (CI spans zero) |

## Trend across the series

| arm | first | last | delta |
|---|---|---|---|
| control | 0.567 | 0.500 | -0.067 |
| sham | 0.567 | 0.458 | -0.108 |
| treatment | 0.500 | 0.800 | +0.300 |

## Per-task detail

Pass rate over k trials. Published in full, losses included.

| task | control E0 | sham E0 | treatment E0 | control E1 | sham E1 | treatment E1 |
|---|---|---|---|---|---|---|
| `eval-01-refund` | 0.60 | 0.40 | 0.20 | 0.40 | 0.40 | 0.60 |
| `eval-02-sweep` | 0.80 | 1.00 | 0.60 | 0.80 | 1.00 | 0.80 |
| `eval-03-interest` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.60 |
| `eval-04-split` | 0.60 | 0.80 | 0.80 | 0.80 | 0.40 | 0.80 |
| `eval-05-statement` | 0.60 | 0.60 | 1.00 | 0.80 | 0.20 | 1.00 |
| `eval-06-merge` | 0.80 | 0.60 | 0.40 | 0.20 | 0.75 | 1.00 |
