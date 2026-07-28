# Scoreboard

Series pinned to `z-ai/glm-4.7-flash` via `openrouter`, Stella `stella 0.5.54` (`4e1f7d8d39c7`), task pool `c6cbc5947ce18680`.

Evaluation pool is held out: it is measured and never learned from. Primary metric is resolution accuracy against a deterministic verifier. Pre-registered threshold for a result: **10%** absolute, paired, CI excluding zero.


## Verdict

**The claim is not supported — no detectable transfer.** treatment does not separate from control by more than the pre-registered threshold at the final epoch.

At the final epoch (E1), treatment − control = -0.200 (95% CI [-0.500, +0.067]).

Treatment moved -0.067 across the series against a control arm that drifted 0.067 on its own — treatment does not clear control's own run-to-run movement. Treatment regression rate: 0.667 (2 task-epochs lost).


**Empirical null.** The control arm does no experience work and is wiped before every evaluation, so its 2 epochs are the same experiment repeated. It ranged 0.067 (sd 0.047) across them, with nothing changed. Any effect smaller than that band is not distinguishable from nothing.

## Resolution accuracy (primary)

Mean per-task pass rate, with a 95% bootstrap CI over tasks.

| arm | E0 | E1 |
|---|---|---|
| **control** | 0.567 [0.333, 0.733] | 0.633 [0.400, 0.833] |
| **sham** | 0.633 [0.333, 0.900] | — |
| **treatment** | 0.500 [0.267, 0.700] | 0.433 [0.267, 0.600] |

## Store growth

Memories carried into each epoch's evaluation. The sham arm must stay comparable to treatment or it is no control at all.

| arm | E0 | E1 |
|---|---|---|
| control | 0 | 0 |
| sham | 0 | — |
| treatment | 0 | 10 |

## Token efficiency — tokens per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 1987566 | 1507493 |
| sham | 1529525 | — |
| treatment | 2140670 | 2543611 |

## Cost — USD per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 0.0270 | 0.0214 |
| sham | 0.0204 | — |
| treatment | 0.0283 | 0.0326 |

## Speed — seconds per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 221.6 | 227.9 |
| sham | 160.7 | — |
| treatment | 224.4 | 218.5 |

## Speed — model calls per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 106.18 | 88.95 |
| sham | 83.63 | — |
| treatment | 126.13 | 136.69 |

## Context efficiency — recalled tokens per model call

| arm | E0 | E1 |
|---|---|---|
| control | 0.5 | 0.6 |
| sham | 0.6 | — |
| treatment | 0.5 | 12.5 |

## Context efficiency — share of recalled frames cited

| arm | E0 | E1 |
|---|---|---|
| control | 0.000 | 0.000 |
| sham | 0.000 | — |
| treatment | 0.000 | 0.000 |

## Memorization check — worked tasks vs. held-out tasks

The evaluation pool is never worked, so it can only show transfer. The experience pool *is* worked, so it can show memorization. Improvement that appears on worked tasks and not on held-out ones is memorization, correctly named — and a context system is supposed to memorize, so seeing it here is expected rather than damning. The divergence between the two columns is the measurement.

| arm | epoch | worked-task pass rate | held-out pass rate | divergence |
|---|---|---|---|---|
| control | E0 | — (n=0) | 0.567 (n=30) | — |
| control | E1 | — (n=0) | 0.633 (n=30) | — |
| sham | E0 | — (n=0) | 0.633 (n=30) | — |
| sham | E1 | — (n=0) | 1.000 (n=1) | — |
| treatment | E0 | 0.600 (n=5) | 0.500 (n=30) | +0.100 |
| treatment | E1 | — (n=0) | 0.433 (n=30) | — |

## Instrument health

Degenerate trials — ones that produced no work at all — are reported separately, because they fail identically to an agent that tried and got it wrong. A null result caused by aborted runs is not a null result about the lifecycle.

| arm | epoch | trials | zero-work | non-completed status | mean calls |
|---|---|---|---|---|---|
| control | E0 | 30 | 0 | 15 | 60.2 |
| control | E1 | 30 | 0 | 11 | 56.3 |
| sham | E0 | 30 | 0 | 12 | 53.0 |
| sham | E1 | 1 | 0 | 0 | 28.0 |
| treatment | E0 | 30 | 1 | 14 | 63.1 |
| treatment | E1 | 30 | 0 | 9 | 59.2 |

## Regression rate

Tasks solved at epoch *N* that fail at *N+1*. A system can learn net-positive while silently breaking what it used to get right.

| arm | transition | solved before | regressed | rate | tasks |
|---|---|---|---|---|---|
| control | E0→E1 | 5 | 1 | 0.200 | eval-06-merge |
| treatment | E0→E1 | 3 | 2 | 0.667 | eval-02-sweep, eval-06-merge |

## Paired comparisons

Same task, same epoch, arm minus arm. Pairing on task has far more power than comparing pool means.

| epoch | comparison | delta | 95% CI | verdict |
|---|---|---|---|---|
| E0 | treatment − control | -0.067 | [-0.267, +0.133] | no detectable difference (CI spans zero) |
| E0 | treatment − sham | -0.133 | [-0.300, +0.033] | no detectable difference (CI spans zero) |
| E0 | sham − control | +0.067 | [-0.133, +0.267] | no detectable difference (CI spans zero) |
| E1 | treatment − control | -0.200 | [-0.500, +0.067] | no detectable difference (CI spans zero) |

## Trend across the series

| arm | first | last | delta |
|---|---|---|---|
| control | 0.567 | 0.633 | +0.067 |
| sham | — | — | — |
| treatment | 0.500 | 0.433 | -0.067 |

## Per-task detail

Pass rate over k trials. Published in full, losses included.

| task | control E0 | sham E0 | treatment E0 | control E1 | sham E1 | treatment E1 |
|---|---|---|---|---|---|---|
| `eval-01-refund` | 0.80 | 0.40 | 0.40 | 0.80 | — | 0.60 |
| `eval-02-sweep` | 0.60 | 1.00 | 0.80 | 1.00 | — | 0.20 |
| `eval-03-interest` | 0.00 | 0.00 | 0.00 | 0.20 | — | 0.40 |
| `eval-04-split` | 0.60 | 1.00 | 0.60 | 0.60 | — | 0.80 |
| `eval-05-statement` | 0.80 | 0.80 | 0.40 | 0.80 | — | 0.40 |
| `eval-06-merge` | 0.60 | 0.60 | 0.80 | 0.40 | — | 0.20 |
