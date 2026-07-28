# Scoreboard

Series pinned to `z-ai/glm-4.7-flash` via `openrouter`, Stella `stella 0.5.68` (`e5bc80dce290`), task pool `a01e7a2175573161`.

Evaluation pool is held out: it is measured and never learned from. Primary metric is resolution accuracy against a deterministic verifier. Pre-registered threshold for a result: **10%** absolute, paired, CI excluding zero.

Reported beside it, and **exploratory rather than pre-registered**: effort per trial and how often the agent had to be steered. Finding 12 showed pass rate saturating on this pool while effort did not — an agent that always succeeds can still take 19 turns or 93 — so a scoreboard that reads only the accuracy row is blind to most of the signal it paid for.


## Verdict

**Accuracy (pre-registered): the claim is not supported — no detectable transfer.** treatment does not separate from control by more than the pre-registered threshold at the final epoch.


**Effort and steering (exploratory): no detectable effort or steering difference (every CI spans zero).** Detail in *Effort* and *Steering* below.

At the final epoch (E2), treatment − control = +0.000 (95% CI [-0.250, +0.222]); treatment − sham = +0.222 (95% CI [+0.028, +0.417]).

Treatment moved -0.028 across the series against a control arm that drifted 0.056 on its own — treatment does not clear control's own run-to-run movement. Treatment regression rate: 0.105 (2 task-epochs lost).


**Empirical null.** The control arm does no experience work and is wiped before every evaluation, so its 3 epochs are the same experiment repeated. It ranged 0.056 (sd 0.032) across them, with nothing changed. Any effect smaller than that band is not distinguishable from nothing.

## Resolution accuracy (primary)

Mean per-task pass rate, with a 95% bootstrap CI over tasks.

| arm | E0 | E1 | E2 |
|---|---|---|---|
| **control** | 0.722 [0.528, 0.889] | 0.778 [0.639, 0.917] | 0.778 [0.611, 0.917] |
| **sham** | 0.778 [0.583, 0.944] | 0.556 [0.389, 0.722] | 0.556 [0.333, 0.778] |
| **treatment** | 0.806 [0.667, 0.944] | 0.750 [0.583, 0.889] | 0.778 [0.583, 0.944] |

## Effort per trial (completed trials only)

What the answer cost, per trial — **not** per solved task. The `*_per_solved` tables further down divide by the number of passes, so they move when accuracy moves and read as an efficiency change that never happened. These are the raw per-trial means.

Restricted to trials with `status == completed`. An abort truncates a run, so a trial that gave up at step 12 records less effort than one that worked honestly to step 60 — including aborts would reward whichever arm quits more. The arms differ on abort rate, and that is reported separately under *Instrument health* rather than smuggled in here.


**model calls** — lower is better

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 46.4 | 49.4 | 54.8 |
| sham | 55.6 | 66.6 | 61.2 |
| treatment | 50.3 | 55.1 | 60.4 |

**cost (USD)** — lower is better

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 0.0085 | 0.0107 | 0.0139 |
| sham | 0.0127 | 0.0228 | 0.0134 |
| treatment | 0.0103 | 0.0172 | 0.0151 |

**output tokens** — lower is better

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 3284 | 4174 | 5076 |
| sham | 4963 | 6406 | 4699 |
| treatment | 3972 | 4628 | 5294 |

### Trials contributing to the effort numbers

`completed / total`. An effort mean resting on a handful of surviving trials is not the same measurement as one resting on all of them.

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 27/36 | 31/36 | 21/36 |
| sham | 31/36 | 22/36 | 27/36 |
| treatment | 32/36 | 30/36 | 31/36 |

## Steering — stuck-loop rate (all trials)

Share of trials whose run ended with the harness's own *stuck-loop* warning: the agent was told it was looping and looped anyway. These are one-shot headless trials, so nobody is there to intervene — this is the closest proxy the design has for *a human had to step in*.

Scored over **all** trials, unlike effort. Looping is only observable on runs that went wrong, so filtering to completed trials would define the outcome out of existence.

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 0.167 | 0.139 | 0.222 |
| sham | 0.111 | 0.222 | 0.139 |
| treatment | 0.083 | 0.111 | 0.111 |

## Paired contrasts on effort and steering

Same task, same epoch, arm minus arm, bootstrapped over tasks — the identical machinery the accuracy contrast uses. Negative favours the first arm on every row: these outcomes are all costs.

`rel` is the delta as a share of the second arm's mean over the same shared tasks. No threshold is applied: none was pre-registered for these axes, and choosing one now, after seeing the probe, would be choosing it knowing the answer.

| epoch | comparison | outcome | delta | 95% CI | rel | n tasks | verdict |
|---|---|---|---|---|---|---|---|
| E0 | treatment − control | model calls | +5.2 | [-2.4, +13.6] | +11.0% | 12 | within noise (CI spans zero) |
| E0 | treatment − control | cost (USD) | +0.0022 | [-0.0001, +0.0047] | +25.0% | 12 | within noise (CI spans zero) |
| E0 | treatment − control | output tokens | +793 | [-448, +2309] | +23.6% | 12 | within noise (CI spans zero) |
| E0 | treatment − control | stuck-loop rate | -0.083 | [-0.222, +0.056] | -50.0% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | model calls | -4.3 | [-14.1, +4.5] | -7.7% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | cost (USD) | -0.0023 | [-0.0074, +0.0016] | -17.4% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | output tokens | -895 | [-2007, +103] | -17.7% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | stuck-loop rate | -0.028 | [-0.167, +0.111] | -25.0% | 12 | within noise (CI spans zero) |
| E0 | sham − control | model calls | +9.5 | [-0.3, +21.9] | +20.3% | 12 | within noise (CI spans zero) |
| E0 | sham − control | cost (USD) | +0.0044 | [+0.0005, +0.0104] | +51.3% | 12 | CI excludes zero |
| E0 | sham − control | output tokens | +1689 | [+209, +3784] | +50.2% | 12 | CI excludes zero |
| E0 | sham − control | stuck-loop rate | -0.056 | [-0.194, +0.083] | -33.3% | 12 | within noise (CI spans zero) |
| E1 | treatment − control | model calls | +6.6 | [-2.4, +17.3] | +13.6% | 11 | within noise (CI spans zero) |
| E1 | treatment − control | cost (USD) | +0.0063 | [-0.0019, +0.0184] | +60.9% | 11 | within noise (CI spans zero) |
| E1 | treatment − control | output tokens | +528 | [-958, +2054] | +13.4% | 11 | within noise (CI spans zero) |
| E1 | treatment − control | stuck-loop rate | -0.028 | [-0.194, +0.139] | -20.0% | 12 | within noise (CI spans zero) |
| E1 | treatment − sham | model calls | -15.8 | [-46.7, +6.7] | -22.4% | 11 | within noise (CI spans zero) |
| E1 | treatment − sham | cost (USD) | -0.0151 | [-0.0549, +0.0096] | -47.7% | 11 | within noise (CI spans zero) |
| E1 | treatment − sham | output tokens | -3316 | [-8359, +609] | -42.6% | 11 | within noise (CI spans zero) |
| E1 | treatment − sham | stuck-loop rate | -0.111 | [-0.306, +0.083] | -50.0% | 12 | within noise (CI spans zero) |
| E1 | sham − control | model calls | +23.4 | [+5.0, +48.4] | +48.3% | 12 | CI excludes zero |
| E1 | sham − control | cost (USD) | +0.0206 | [+0.0026, +0.0523] | +199.7% | 12 | CI excludes zero |
| E1 | sham − control | output tokens | +3957 | [+638, +8495] | +98.7% | 12 | CI excludes zero |
| E1 | sham − control | stuck-loop rate | +0.083 | [-0.056, +0.222] | +60.0% | 12 | within noise (CI spans zero) |
| E2 | treatment − control | model calls | +3.9 | [-14.0, +19.3] | +6.7% | 12 | within noise (CI spans zero) |
| E2 | treatment − control | cost (USD) | -0.0012 | [-0.0158, +0.0090] | -7.0% | 12 | within noise (CI spans zero) |
| E2 | treatment − control | output tokens | -163 | [-3148, +2548] | -2.7% | 12 | within noise (CI spans zero) |
| E2 | treatment − control | stuck-loop rate | -0.111 | [-0.278, +0.056] | -50.0% | 12 | within noise (CI spans zero) |
| E2 | treatment − sham | model calls | +0.5 | [-12.4, +12.9] | +0.9% | 11 | within noise (CI spans zero) |
| E2 | treatment − sham | cost (USD) | +0.0028 | [-0.0032, +0.0098] | +20.9% | 11 | within noise (CI spans zero) |
| E2 | treatment − sham | output tokens | +1417 | [-1206, +4860] | +29.9% | 11 | within noise (CI spans zero) |
| E2 | treatment − sham | stuck-loop rate | -0.028 | [-0.139, +0.083] | -20.0% | 12 | within noise (CI spans zero) |
| E2 | sham − control | model calls | +9.8 | [-3.9, +25.2] | +18.6% | 11 | within noise (CI spans zero) |
| E2 | sham − control | cost (USD) | +0.0023 | [-0.0024, +0.0071] | +20.7% | 11 | within noise (CI spans zero) |
| E2 | sham − control | output tokens | -439 | [-4234, +2495] | -8.5% | 11 | within noise (CI spans zero) |
| E2 | sham − control | stuck-loop rate | -0.083 | [-0.278, +0.083] | -37.5% | 12 | within noise (CI spans zero) |

> **45 contrasts are computed on this page** (9 on accuracy, 36 on effort and steering). At alpha = 0.05 the family-wise error rate is **~90%** — several intervals excluding zero by chance alone is the expectation, not the exception. More contrasts have already been run across findings 10–12, so the true family is larger than this page. What earns confidence is not one interval but independent measures agreeing in direction and size on the same arm, and then replicating. Read this table that way.


## Store growth

Memories carried into each epoch's evaluation. The sham arm must stay comparable to treatment or it is no control at all.

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 0 | 0 | 0 |
| sham | 0 | 8 | 17 |
| treatment | 0 | 9 | 13 |

## Per-solved-task ratios (kept for continuity — read with care)

These divide total effort by the number of *passes*, so they conflate effort with correctness: an arm that solves one more task looks more efficient without having changed how it works. The per-trial tables above are the ones to read for effort. Retained because series 001 and 002 were published on them.


## Token efficiency — tokens per solved task

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 1533975 | 899654 | 2098495 |
| sham | 1213961 | 3886607 | 2092043 |
| treatment | 913967 | 1232092 | 1410706 |

## Cost — USD per solved task

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 0.0191 | 0.0129 | 0.0289 |
| sham | 0.0166 | 0.0487 | 0.0292 |
| treatment | 0.0148 | 0.0221 | 0.0208 |

## Speed — seconds per solved task

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 164.9 | 142.6 | 250.2 |
| sham | 180.9 | 407.0 | 375.8 |
| treatment | 162.7 | 221.4 | 190.3 |

## Speed — model calls per solved task

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 83.50 | 60.68 | 99.43 |
| sham | 74.25 | 149.00 | 118.35 |
| treatment | 61.07 | 75.85 | 81.71 |

## Context efficiency — recalled tokens per model call

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 0.8 | 1.0 | 0.6 |
| sham | 0.8 | 5.3 | 8.9 |
| treatment | 0.9 | 8.7 | 9.7 |

## Context efficiency — share of recalled frames cited

| arm | E0 | E1 | E2 |
|---|---|---|---|
| control | 0.000 | 0.000 | 0.000 |
| sham | 0.000 | 0.303 | 0.500 |
| treatment | 0.000 | 0.009 | 0.100 |

## Memorization check — worked tasks vs. held-out tasks

The evaluation pool is never worked, so it can only show transfer. The experience pool *is* worked, so it can show memorization. Improvement that appears on worked tasks and not on held-out ones is memorization, correctly named — and a context system is supposed to memorize, so seeing it here is expected rather than damning. The divergence between the two columns is the measurement.

| arm | epoch | worked-task pass rate | held-out pass rate | divergence |
|---|---|---|---|---|
| control | E0 | — (n=0) | 0.722 (n=36) | — |
| control | E1 | — (n=0) | 0.778 (n=36) | — |
| control | E2 | — (n=0) | 0.778 (n=36) | — |
| sham | E0 | — (n=0) | 0.778 (n=36) | — |
| sham | E1 | — (n=0) | 0.556 (n=36) | — |
| sham | E2 | — (n=0) | 0.556 (n=36) | — |
| treatment | E0 | 1.000 (n=5) | 0.806 (n=36) | +0.194 |
| treatment | E1 | 0.800 (n=5) | 0.750 (n=36) | +0.050 |
| treatment | E2 | — (n=0) | 0.778 (n=36) | — |

## Instrument health

Degenerate trials — ones that produced no work at all — are reported separately, because they fail identically to an agent that tried and got it wrong. A null result caused by aborted runs is not a null result about the lifecycle.

| arm | epoch | trials | zero-work | non-completed status | mean calls |
|---|---|---|---|---|---|
| control | E0 | 36 | 0 | 9 | 60.3 |
| control | E1 | 36 | 0 | 5 | 47.2 |
| control | E2 | 36 | 1 | 15 | 77.3 |
| sham | E0 | 36 | 0 | 5 | 57.8 |
| sham | E1 | 36 | 1 | 14 | 82.8 |
| sham | E2 | 36 | 2 | 9 | 65.8 |
| treatment | E0 | 36 | 1 | 4 | 49.2 |
| treatment | E1 | 36 | 1 | 6 | 56.9 |
| treatment | E2 | 36 | 0 | 5 | 63.6 |

## Regression rate

Tasks solved at epoch *N* that fail at *N+1*. A system can learn net-positive while silently breaking what it used to get right.

| arm | transition | solved before | regressed | rate | tasks |
|---|---|---|---|---|---|
| control | E0→E1 | 9 | 0 | 0.000 | — |
| control | E1→E2 | 10 | 1 | 0.100 | eval-08-installments |
| sham | E0→E1 | 10 | 4 | 0.400 | eval-02-sweep, eval-04-split, eval-05-statement, eval-09-reconcile |
| sham | E1→E2 | 6 | 2 | 0.333 | eval-06-merge, eval-07-tax |
| treatment | E0→E1 | 10 | 2 | 0.200 | eval-02-sweep, eval-11-share |
| treatment | E1→E2 | 9 | 0 | 0.000 | — |

## Paired comparisons — accuracy (primary)

Same task, same epoch, arm minus arm. Pairing on task has far more power than comparing pool means.

| epoch | comparison | delta | 95% CI | verdict |
|---|---|---|---|---|
| E0 | treatment − control | +0.083 | [-0.111, +0.250] | no detectable difference (CI spans zero) |
| E0 | treatment − sham | +0.028 | [-0.139, +0.167] | no detectable difference (CI spans zero) |
| E0 | sham − control | +0.056 | [-0.083, +0.167] | no detectable difference (CI spans zero) |
| E1 | treatment − control | -0.028 | [-0.222, +0.167] | no detectable difference (CI spans zero) |
| E1 | treatment − sham | +0.194 | [+0.000, +0.389] | difference exceeds the pre-registered threshold |
| E1 | sham − control | -0.222 | [-0.417, -0.028] | difference exceeds the pre-registered threshold |
| E2 | treatment − control | +0.000 | [-0.250, +0.222] | no detectable difference (CI spans zero) |
| E2 | treatment − sham | +0.222 | [+0.028, +0.417] | difference exceeds the pre-registered threshold |
| E2 | sham − control | -0.222 | [-0.389, -0.028] | difference exceeds the pre-registered threshold |

## Trend across the series

| arm | first | last | delta |
|---|---|---|---|
| control | 0.722 | 0.778 | +0.056 |
| sham | 0.778 | 0.556 | -0.222 |
| treatment | 0.806 | 0.778 | -0.028 |

## Per-task detail

Pass rate over k trials. Published in full, losses included.

| task | control E0 | sham E0 | treatment E0 | control E1 | sham E1 | treatment E1 | control E2 | sham E2 | treatment E2 |
|---|---|---|---|---|---|---|---|---|---|
| `eval-01-refund` | 0.67 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `eval-02-sweep` | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.33 | 1.00 | 0.33 | 0.00 |
| `eval-03-interest` | 0.33 | 0.00 | 0.33 | 0.33 | 0.33 | 0.67 | 0.33 | 0.00 | 0.67 |
| `eval-04-split` | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.67 | 1.00 | 1.00 | 0.67 |
| `eval-05-statement` | 1.00 | 0.67 | 1.00 | 0.67 | 0.33 | 1.00 | 1.00 | 0.67 | 1.00 |
| `eval-06-merge` | 1.00 | 1.00 | 0.33 | 1.00 | 0.67 | 0.33 | 0.67 | 0.00 | 0.33 |
| `eval-07-tax` | 0.67 | 1.00 | 0.67 | 1.00 | 0.67 | 1.00 | 0.67 | 0.33 | 1.00 |
| `eval-08-installments` | 0.00 | 0.33 | 0.67 | 0.67 | 0.00 | 0.67 | 0.33 | 0.00 | 0.67 |
| `eval-09-reconcile` | 0.67 | 1.00 | 1.00 | 0.67 | 0.33 | 1.00 | 1.00 | 0.67 | 1.00 |
| `eval-10-cap` | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `eval-11-share` | 0.33 | 0.67 | 0.67 | 0.33 | 0.67 | 0.33 | 0.33 | 1.00 | 1.00 |
| `eval-12-largest` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 |
