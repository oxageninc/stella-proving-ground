# Scoreboard

Series pinned to `z-ai/glm-4.7-flash` via `openrouter`, Stella `stella 0.5.73` (`7a1753754697`), task pool `a01e7a2175573161`.

Evaluation pool is held out: it is measured and never learned from. Primary metric is resolution accuracy against a deterministic verifier. Pre-registered threshold for a result: **10%** absolute, paired, CI excluding zero.

Reported beside it, and **exploratory rather than pre-registered**: effort per trial and how often the agent had to be steered. Finding 12 showed pass rate saturating on this pool while effort did not — an agent that always succeeds can still take 19 turns or 93 — so a scoreboard that reads only the accuracy row is blind to most of the signal it paid for.


## Verdict

**Accuracy (pre-registered): the claim is not supported — no detectable transfer.** treatment does not separate from control by more than the pre-registered threshold at the final epoch.


**Effort and steering (exploratory): treatment is cheaper than control on cost_usd.** Detail in *Effort* and *Steering* below.

At the final epoch (E1), treatment − control = -0.306 (95% CI [-0.528, -0.083]); treatment − sham = -0.222 (95% CI [-0.472, +0.028]).

Treatment moved -0.333 across the series against a control arm that drifted 0.111 on its own — treatment clears control's own run-to-run movement. Treatment regression rate: 0.545 (6 task-epochs lost).


**Empirical null.** The control arm does no experience work and is wiped before every evaluation, so its 2 epochs are the same experiment repeated. It ranged 0.111 (sd 0.079) across them, with nothing changed. Any effect smaller than that band is not distinguishable from nothing.

> **This series is underpowered for its own threshold.** Control's no-op range (0.111) exceeds the pre-registered 10% effect size, so a true effect at exactly that size could not be resolved here. Reported rather than adjusted after the fact: the fix is more evaluation tasks, not a friendlier threshold.


## Resolution accuracy (primary)

Mean per-task pass rate, with a 95% bootstrap CI over tasks.

| arm | E0 | E1 |
|---|---|---|
| **control** | 0.722 [0.500, 0.917] | 0.833 [0.583, 1.000] |
| **sham** | 0.611 [0.389, 0.806] | 0.750 [0.556, 0.917] |
| **treatment** | 0.861 [0.722, 0.972] | 0.528 [0.333, 0.750] |

## Effort per trial (completed trials only)

What the answer cost, per trial — **not** per solved task. The `*_per_solved` tables further down divide by the number of passes, so they move when accuracy moves and read as an efficiency change that never happened. These are the raw per-trial means.

Restricted to trials with `status == completed`. An abort truncates a run, so a trial that gave up at step 12 records less effort than one that worked honestly to step 60 — including aborts would reward whichever arm quits more. The arms differ on abort rate, and that is reported separately under *Instrument health* rather than smuggled in here.


**model calls** — lower is better

| arm | E0 | E1 |
|---|---|---|
| control | 48.8 | 48.7 |
| sham | 41.0 | 58.9 |
| treatment | 50.8 | 57.3 |

**cost (USD)** — lower is better

| arm | E0 | E1 |
|---|---|---|
| control | 0.0455 | 0.0440 |
| sham | 0.0352 | 0.0181 |
| treatment | 0.0376 | 0.0182 |

**output tokens** — lower is better

| arm | E0 | E1 |
|---|---|---|
| control | 4725 | 5858 |
| sham | 2865 | 5925 |
| treatment | 4702 | 4301 |

### Trials contributing to the effort numbers

`completed / total`. An effort mean resting on a handful of surviving trials is not the same measurement as one resting on all of them.

| arm | E0 | E1 |
|---|---|---|
| control | 26/36 | 29/36 |
| sham | 23/36 | 29/36 |
| treatment | 29/36 | 27/36 |

## Steering — stuck-loop rate (all trials)

Share of trials whose run ended with the harness's own *stuck-loop* warning: the agent was told it was looping and looped anyway. These are one-shot headless trials, so nobody is there to intervene — this is the closest proxy the design has for *a human had to step in*.

Scored over **all** trials, unlike effort. Looping is only observable on runs that went wrong, so filtering to completed trials would define the outcome out of existence.

| arm | E0 | E1 |
|---|---|---|
| control | 0.222 | 0.139 |
| sham | 0.306 | 0.139 |
| treatment | 0.139 | 0.194 |

## Paired contrasts on effort and steering

Same task, same epoch, arm minus arm, bootstrapped over tasks — the identical machinery the accuracy contrast uses. Negative favours the first arm on every row: these outcomes are all costs.

`rel` is the delta as a share of the second arm's mean over the same shared tasks. No threshold is applied: none was pre-registered for these axes, and choosing one now, after seeing the probe, would be choosing it knowing the answer.

| epoch | comparison | outcome | delta | 95% CI | rel | n tasks | verdict |
|---|---|---|---|---|---|---|---|
| E0 | treatment − control | model calls | -0.1 | [-10.2, +9.6] | -0.1% | 12 | within noise (CI spans zero) |
| E0 | treatment − control | cost (USD) | -0.0111 | [-0.0278, +0.0066] | -24.7% | 12 | within noise (CI spans zero) |
| E0 | treatment − control | output tokens | -449 | [-1701, +1030] | -9.6% | 12 | within noise (CI spans zero) |
| E0 | treatment − control | stuck-loop rate | -0.083 | [-0.306, +0.139] | -37.5% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | model calls | +4.5 | [-7.5, +16.8] | +10.2% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | cost (USD) | -0.0043 | [-0.0209, +0.0114] | -11.2% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | output tokens | +1178 | [-519, +3244] | +38.7% | 12 | within noise (CI spans zero) |
| E0 | treatment − sham | stuck-loop rate | -0.167 | [-0.361, +0.000] | -54.5% | 12 | within noise (CI spans zero) |
| E0 | sham − control | model calls | -4.5 | [-12.3, +3.2] | -9.4% | 12 | within noise (CI spans zero) |
| E0 | sham − control | cost (USD) | -0.0068 | [-0.0185, +0.0038] | -15.2% | 12 | within noise (CI spans zero) |
| E0 | sham − control | output tokens | -1627 | [-3038, -633] | -34.8% | 12 | CI excludes zero |
| E0 | sham − control | stuck-loop rate | +0.083 | [-0.111, +0.306] | +37.5% | 12 | within noise (CI spans zero) |
| E1 | treatment − control | model calls | +8.2 | [-0.5, +17.3] | +16.8% | 11 | within noise (CI spans zero) |
| E1 | treatment − control | cost (USD) | -0.0292 | [-0.0365, -0.0228] | -65.3% | 11 | CI excludes zero |
| E1 | treatment − control | output tokens | -1604 | [-3898, +595] | -26.4% | 11 | within noise (CI spans zero) |
| E1 | treatment − control | stuck-loop rate | +0.056 | [-0.056, +0.167] | +40.0% | 12 | within noise (CI spans zero) |
| E1 | treatment − sham | model calls | -0.2 | [-9.7, +8.8] | -0.3% | 12 | within noise (CI spans zero) |
| E1 | treatment − sham | cost (USD) | +0.0041 | [-0.0071, +0.0201] | +22.3% | 12 | within noise (CI spans zero) |
| E1 | treatment − sham | output tokens | -1233 | [-3909, +1052] | -21.1% | 12 | within noise (CI spans zero) |
| E1 | treatment − sham | stuck-loop rate | +0.056 | [-0.111, +0.222] | +40.0% | 12 | within noise (CI spans zero) |
| E1 | sham − control | model calls | +11.0 | [+0.2, +20.7] | +22.4% | 11 | CI excludes zero |
| E1 | sham − control | cost (USD) | -0.0265 | [-0.0343, -0.0179] | -59.3% | 11 | CI excludes zero |
| E1 | sham − control | output tokens | -60 | [-3412, +3360] | -1.0% | 11 | within noise (CI spans zero) |
| E1 | sham − control | stuck-loop rate | +0.000 | [-0.194, +0.167] | +0.0% | 12 | within noise (CI spans zero) |

> **30 contrasts are computed on this page** (6 on accuracy, 24 on effort and steering). At alpha = 0.05 the family-wise error rate is **~79%** — several intervals excluding zero by chance alone is the expectation, not the exception. More contrasts have already been run across findings 10–12, so the true family is larger than this page. What earns confidence is not one interval but independent measures agreeing in direction and size on the same arm, and then replicating. Read this table that way.


## Store growth

Memories carried into each epoch's evaluation. The sham arm must stay comparable to treatment or it is no control at all.

| arm | E0 | E1 |
|---|---|---|
| control | 0 | 0 |
| sham | 0 | 13 |
| treatment | 0 | 9 |

## Per-solved-task ratios (kept for continuity — read with care)

These divide total effort by the number of *passes*, so they conflate effort with correctness: an arm that solves one more task looks more efficient without having changed how it works. The per-trial tables above are the ones to read for effort. Retained because series 001 and 002 were published on them.


## Token efficiency — tokens per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 1120388 | 1083590 |
| sham | 1116726 | 1522843 |
| treatment | 1121316 | 1809825 |

## Cost — USD per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 0.0665 | 0.0627 |
| sham | 0.0575 | 0.0267 |
| treatment | 0.0535 | 0.0390 |

## Speed — seconds per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 281.6 | 270.0 |
| sham | 300.7 | 374.9 |
| treatment | 255.3 | 494.2 |

## Speed — model calls per solved task

| arm | E0 | E1 |
|---|---|---|
| control | 69.12 | 63.27 |
| sham | 74.86 | 89.11 |
| treatment | 63.52 | 113.11 |

## Context efficiency — recalled tokens per model call

| arm | E0 | E1 |
|---|---|---|
| control | 0.9 | 0.8 |
| sham | 1.0 | 6.3 |
| treatment | 0.9 | 8.9 |

## Context efficiency — share of recalled frames cited

| arm | E0 | E1 |
|---|---|---|
| control | 0.000 | 0.000 |
| sham | 0.000 | 0.336 |
| treatment | 0.000 | 0.126 |

## Memorization check — worked tasks vs. held-out tasks

The evaluation pool is never worked, so it can only show transfer. The experience pool *is* worked, so it can show memorization. Improvement that appears on worked tasks and not on held-out ones is memorization, correctly named — and a context system is supposed to memorize, so seeing it here is expected rather than damning. The divergence between the two columns is the measurement.

| arm | epoch | worked-task pass rate | held-out pass rate | divergence |
|---|---|---|---|---|
| control | E0 | — (n=0) | 0.722 (n=36) | — |
| control | E1 | — (n=0) | 0.833 (n=36) | — |
| sham | E0 | — (n=0) | 0.611 (n=36) | — |
| sham | E1 | — (n=0) | 0.750 (n=36) | — |
| treatment | E0 | 1.000 (n=5) | 0.861 (n=36) | +0.139 |
| treatment | E1 | 0.800 (n=5) | 0.528 (n=36) | +0.272 |

## Instrument health

Degenerate trials — ones that produced no work at all — are reported separately, because they fail identically to an agent that tried and got it wrong. A null result caused by aborted runs is not a null result about the lifecycle.

| arm | epoch | trials | zero-work | non-completed status | mean calls |
|---|---|---|---|---|---|
| control | E0 | 36 | 1 | 10 | 49.9 |
| control | E1 | 36 | 1 | 7 | 52.7 |
| sham | E0 | 36 | 1 | 13 | 45.8 |
| sham | E1 | 36 | 0 | 7 | 66.8 |
| treatment | E0 | 36 | 0 | 7 | 54.7 |
| treatment | E1 | 36 | 1 | 9 | 59.7 |

## Regression rate

Tasks solved at epoch *N* that fail at *N+1*. A system can learn net-positive while silently breaking what it used to get right.

| arm | transition | solved before | regressed | rate | tasks |
|---|---|---|---|---|---|
| control | E0→E1 | 9 | 1 | 0.111 | eval-03-interest |
| sham | E0→E1 | 8 | 1 | 0.125 | eval-11-share |
| treatment | E0→E1 | 11 | 6 | 0.545 | eval-02-sweep, eval-03-interest, eval-05-statement, eval-06-merge, eval-07-tax, eval-08-installments |

## Paired comparisons — accuracy (primary)

Same task, same epoch, arm minus arm. Pairing on task has far more power than comparing pool means.

| epoch | comparison | delta | 95% CI | verdict |
|---|---|---|---|---|
| E0 | treatment − control | +0.139 | [-0.111, +0.389] | no detectable difference (CI spans zero) |
| E0 | treatment − sham | +0.250 | [-0.000, +0.500] | no detectable difference (CI spans zero) |
| E0 | sham − control | -0.111 | [-0.306, +0.111] | no detectable difference (CI spans zero) |
| E1 | treatment − control | -0.306 | [-0.528, -0.083] | difference exceeds the pre-registered threshold |
| E1 | treatment − sham | -0.222 | [-0.472, +0.028] | no detectable difference (CI spans zero) |
| E1 | sham − control | -0.083 | [-0.222, +0.056] | no detectable difference (CI spans zero) |

## Trend across the series

| arm | first | last | delta |
|---|---|---|---|
| control | 0.722 | 0.833 | +0.111 |
| sham | 0.611 | 0.750 | +0.139 |
| treatment | 0.861 | 0.528 | -0.333 |

## Per-task detail

Pass rate over k trials. Published in full, losses included.

| task | control E0 | sham E0 | treatment E0 | control E1 | sham E1 | treatment E1 |
|---|---|---|---|---|---|---|
| `eval-01-refund` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `eval-02-sweep` | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 | 0.00 |
| `eval-03-interest` | 0.67 | 0.00 | 0.67 | 0.00 | 0.33 | 0.00 |
| `eval-04-split` | 1.00 | 1.00 | 0.33 | 1.00 | 1.00 | 0.33 |
| `eval-05-statement` | 0.67 | 0.33 | 1.00 | 1.00 | 0.67 | 0.33 |
| `eval-06-merge` | 1.00 | 0.33 | 1.00 | 1.00 | 0.67 | 0.33 |
| `eval-07-tax` | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 | 0.33 |
| `eval-08-installments` | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.33 |
| `eval-09-reconcile` | 0.33 | 0.67 | 1.00 | 1.00 | 1.00 | 0.67 |
| `eval-10-cap` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `eval-11-share` | 0.00 | 0.67 | 0.67 | 1.00 | 0.33 | 1.00 |
| `eval-12-largest` | 1.00 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 |

