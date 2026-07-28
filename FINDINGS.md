# Findings

Defects and design facts found while building the harness, in the order they
would bite anyone else trying to measure this. Each one is stated with the
evidence that produced it, because several of them are invisible from the
outside — they make the lifecycle *appear* to run while producing nothing.

Observations were made against Stella `0.5.51` (`ac5b344b`) and `0.5.54`
(`4e1f7d8d`), on the headless `stella run` path. The binary was rebuilt from
`main` partway through this work; series 001 is pinned to `0.5.54`
(`binary_sha256` `160d0354cbfe4183`) and every finding below was either observed
on, or re-confirmed against, that build.

---

## 1. `--model` is silently overridden, and the envelope reports the wrong model

**Severity: high — it defeats pinning, which is the premise of a longitudinal series.**

`~/.stella/settings.json`'s `agent_engine_config.pipeline_worker_model`
outranks the `--model` flag on the pipeline path. The flag is accepted, no
warning is emitted, and the JSON envelope's top-level `model` field reports the
model that was *requested* rather than the one that ran.

Re-confirmed on `0.5.54`, the build series 001 is pinned to. Asking for
`openrouter/z-ai/glm-4.7-flash` with a global settings file present, on a task
whose entire content is "add a docstring to f in a.py":

```
top-level "model" field: openrouter/z-ai/glm-4.7-flash     <- what was asked for
step_usage[0] role=triage  model=anthropic/claude-haiku-4.5 <- what ran
step_usage[1] role=worker  model=anthropic/claude-fable-5
...
cost_usd: 0.16788   <- for adding one docstring
```

With the model actually pinned (via a workspace-local `.stella/settings.json`),
the identical task cost `$0.0010781` — a **220x** cost difference between what
the caller asked for and what it got.

Issue #755 requires that "a model change invalidates a series". A harness that
pinned with `--model` and verified with the envelope would satisfy that
requirement on paper while silently running a different model throughout. This
harness therefore pins via workspace settings and reads the model back from
per-call `step_usage` events (`config.observed_models`).

**Suggested fix:** either have `--model` win, or refuse to run when both are
set, or — at minimum — report the resolved model in the envelope rather than the
requested one.

---

## 2. Reflection silently records nothing unless the model emits bare JSON

**Severity: high — it starves the entire lifecycle, with no error anywhere.**

Reflection is the only source of observations, observations are the only source
of proposals, and proposals are the only route to durable memory. The
reflection prompt demands a bare JSON array. A model that opens with
chain-of-thought prose produces an unparseable response, which is reported as
`"recorded": 0` with `"error": null` — indistinguishable from "this turn held
no lessons".

The reflection call is also capped at 512 output tokens, so a model that thinks
before answering exhausts the cap mid-thought and can never reach the JSON:

```
role: reflection  model: z-ai/glm-4.7-flash  output_tokens: 512
OUTPUT TEXT: 1.  **Analyze the Request:**
    *   **Role:** Self-reflection module.
    *   **Output Format:** JSON array (max 3 items).
    ...
reflection.recorded = 0, error = null, reflections.jsonl not created
```

Measured across four models on the identical task:

| reflection model | `recorded` | `reflections.jsonl` |
|---|---|---|
| `z-ai/glm-4.7-flash` | 0 | absent |
| `deepseek/deepseek-v4-flash` | 0 | absent |
| `google/gemini-2.5-flash-lite` | 2 | 2 lines |
| `anthropic/claude-haiku-4.5` | 3 | 3 lines |

So on a flash-tier model the adaptive-context lifecycle produces **zero durable
records, ever**, and reports no error while doing it. This directly answers one
of #755's open questions ("whether flash-tier models show the same effect
direction as frontier ones"): on the flash tier tested there is no effect to
have a direction, because nothing is ever learned.

There is no `reflection` agent kind — `EngineAgentKind` is
`{Default, Worker, Judge, Triage}` (`stella-cli/src/settings.rs:196`) — so
reflection follows `default_model`. That turns out to be usable as a workaround:
pinning `default_model` to a model that emits JSON while
`pipeline_worker_model` stays on a competent coder gives a working lifecycle at
flash-tier cost. This harness does exactly that.

**Suggested fix:** treat an unparseable reflection as an error rather than as
zero lessons; raise or remove the 512-token cap; and consider a dedicated
`reflection` agent kind so the role can be pinned without hijacking
`default_model`.

---

## 3. An untrusted workspace skips the whole mining loop

**Severity: high — the lifecycle produces nothing in any workspace without project trust.**

> **Corrected.** This finding was first written as "observations are never
> extracted on the `stella run` path", which was the symptom rather than the
> cause and would have sent anyone fixing it to the wrong place. The real
> condition is workspace trust, established while writing the fix
> ([stella#766](https://github.com/macanderson/stella/pull/766)). The
> measurements below are unchanged; the diagnosis is.

`SessionMemory::auto_create_skills` opened with an authority gate:

```rust
if !self.include_workspace_skills {
    return;
}
```

where `include_workspace_skills` is `authority.project_prompts_allowed` — false
for any workspace without project trust. The comment explains it in terms of
skill *files*: without the workspace scope the loader is handed an empty skills
dir, so a skill written there would never be read back.

But the early return also skipped everything upstream of that write:
attribution (`extract_context_uses`), retirement (`retire_failing_context`),
observation extraction (`extract_reflection_observations`) and proposal
induction. None of those touch the workspace skills directory — they write to
the session's own `.stella/private/context.db`, which the *same function* has
already written reflection memories to a few lines earlier. So the gate did not
protect the store; it made the store's contents inconsistent.

The consequence is that in every fresh checkout, every eval sandbox and every
CI job, reflection mines lessons every turn and they go nowhere:

```
exp run 0: reflections=1  store={memories:1, episodes:1, context_records:0}
exp run 1: reflections=2  store={memories:2, episodes:2, context_records:0}
exp run 2: reflections=2  store={memories:2, episodes:2, context_records:0}
```

Running the offline command by hand does the extraction immediately, which is
what originally made this look like a missing call on the run path:

```
$ stella proposals refresh
  ✦ 3 new observation(s), 3 observation(s) total, 0 proposal(s) (0 new)
```

**Fixed** in stella#766: the gate moved onto `write_candidates` and
`induce_rules` — the two writes it actually describes — so no skill or rule
file lands in a workspace the session may not read, while the ledger half of
the lifecycle runs. The pre-existing guarantee
(`auto_creation_never_writes_into_a_skills_dir_the_session_may_not_read`) still
passes, and a new test asserts the other half.

This harness still enables `pump_proposals`, because the series is pinned to a
binary built before the fix.

---

## 3b. Original symptom, retained for the record

**The observe phase does not close automatically on the `stella run` path.**

Even with a model whose reflection parses, lessons accumulate in
`.stella/private/reflections.jsonl` and are never advanced into
`context_records`. Three sequential experience runs sharing one store:

```
exp run 0: reflections=1  store={memories:1, episodes:1, context_records:0}
exp run 1: reflections=2  store={memories:2, episodes:2, context_records:0}
exp run 2: reflections=2  store={memories:2, episodes:2, context_records:0}
```

`context_records` stays at zero, and `context_extraction_cursor` stays empty.
Running the documented offline command by hand does the extraction immediately:

```
$ stella proposals refresh
  ✦ 3 new observation(s), 3 observation(s) total, 0 proposal(s) (0 new)
```

So on the primary headless surface the lifecycle stops after reflection unless
a human runs `proposals refresh`. This harness calls it after every experience
block and records `pump_proposals` in the pinned config, because without it the
treatment arm carries no durable content and the experiment would be measuring
plumbing rather than transfer.

---

## 4. Governance cannot promote from a single run

`0 proposal(s)` above is not a bug, but it constrains any experiment. Promotion
requires `min_distinct_tasks: 3` **and** `min_observations: 3`, and task
identity is approximated per turn — `task_id_for` returns `turn:<occurred_at>`,
where every lesson from one reflection call shares one timestamp
(`stella-cli/src/memory/observations.rs:48-68`). Three lessons from one turn
therefore count as **one** task, not three, and no amount of work inside a
single run can promote anything.

The comment in that file states the limitation plainly and notes that
`ReflectionLesson::task_id` exists precisely so a caller with a real task
boundary can supply one — "nothing populates it yet". A proving ground is
exactly such a caller, which is the upstreamable opportunity #755 anticipated.

---

## 4b. RETRACTED — "nothing ever cites a recalled memory"

This repo previously reported `cited_frames = 0` in every trial of two full
series and concluded the attribution loop never fires. **That was a bug in this
harness, not a finding about Stella.**

The runner counted a `memory_citation` agent event. No such event exists —
citations are rows in `store.db.memory_citations`. The metric was therefore
structurally zero and could never have been anything else, which is the worst
kind of instrument error: it produced a confident number that looked like
evidence.

Corrected count, read from the store:

```
series-001/treatment: 1      series-001/sham: 0
series-002/treatment: 0      series-002/sham: 0
```

One citation across two series. Still very low, and probably worth
investigating — but "rare" and "structurally impossible" are different claims,
and only the first is supported. `runner.count_citations` now reads the store.

The general lesson is the same one as finding 7: a metric nobody has
negative-controlled is not a measurement. The verifiers here were controlled in
both directions from the start and caught a real contamination bug; the
telemetry counters were not, and this one lied for two full series.

---

## 5. The in-process A/B recall control never fires headlessly

#755 proposes reusing Stella's `maybe_suppress_recall` / `ab_control_turn` as a
free within-run control. It is called from exactly one site —
`stella-cli/src/agent.rs:985`, inside `run_interactive`'s plain-prompt branch.
`stella run`, `stella goal`, `stella arena` and the Command Deck never produce a
control turn, so no episode is ever tagged `[ab-control]` on any headless path.

The mechanism is also deterministic rather than probabilistic — every 10th turn
of a session (`AB_RECALL_RATE = 10`, a compile-time constant with no env var or
flag) — so it cannot be reconfigured without a rebuild.

For a batch harness the feature is unavailable, and this harness does not use
it. The between-arm control replaces it.

---

## 6. The lifecycle loop did not close end-to-end on `main` — since fixed upstream

> **Corrected.** True when first observed at `ac5b344b`; **no longer true.**
> Phase 4 merged in the interim and is present at `eeb714dc` (v0.5.57), where
> `stella-cli/src/memory/uses.rs` exists and its suite runs
> (`memory::uses::tests::the_loop_closes_a_repeatedly_unhelpful_record_is_retired_and_restorable`,
> among others). Recorded rather than deleted because the original observation
> was the basis for saying #755's opening premise did not hold, and a reader
> comparing against a current checkout deserves to know it now does.

#755 opens by stating that the loop closes end to end (#469: observe → propose
→ govern → select → attribute → retire). At `ac5b344b` the last two phases were
absent: `ContextUse` and `ContextUseFeedback` record kinds were declared
(`stella-core/src/context_record/kind.rs:28-29`) with their types defined, but
nothing outside tests constructed or appended them, and Phase 4 (#715) lived in
an unmerged worktree.

What remains true for series 001 is narrower and worth stating plainly: the
series is pinned to a binary at `4e1f7d8d`, and **attribution and retirement
never ran in it**, because finding #3's authority gate skipped
`extract_context_uses` and `retire_failing_context` in every trial workspace.
So the regression-rate metric has no retirement to catch in this series. It is
reported anyway, so the baseline exists for the first series run against a
binary carrying stella#766.

---

## 7. The agent reached the harness — containment is not automatic

**Severity: critical. It voided a whole series, and it was silent.**

This one is the harness's own bug rather than Stella's, but it is worth
recording because #755 states "the agent cannot reach the harness" as a design
requirement, and the natural implementation does not satisfy it.

Trial workspaces originally lived at `results/<series>/work/<trial>/` — inside
this repository. Stella's project discovery walks *up* from the working
directory to the enclosing repo, so the agent's reachable tree included
`tasks/corpus/`, `tasks/evaluation/*/verify.py`, and the results themselves.

An agent working the `interest` task wrote its handler into the **pristine
corpus** at `tasks/corpus/ledgerctl/ledgerctl/commands/interest.py` and
registered it in the corpus's `registry.py`. Every subsequent trial's
`materialize` then copied that corpus — implementation included — into the
fresh workspace, so `eval-03-interest` passed *before the agent did anything*.
The same happened for `sweep`.

Two things made it dangerous rather than merely annoying:

1. **It looks like success.** The affected tasks went to a 100% pass rate. A
   contaminated series does not error; it produces the most encouraging
   possible result.
2. **It got committed.** A `git add -A` while a trial was in flight captured
   the agent's `sweep.py` into a harness commit, so the contamination outlived
   the run that caused it.

It was caught only because the negative control (`no verifier may pass on an
untouched corpus`) is a standing test rather than a one-off check made while
writing the verifiers. Had it been a one-off, every number in this repo would
have been wrong and plausible.

Fixed three ways: workspaces and per-arm stores now live outside the repository
(`tasks.default_work_root`), the corpus digest is asserted before and after
every trial (`tasks.corpus_digest`, raising `CorpusTampered`), and
`test_corpus_is_pristine` fails the suite if a contaminated corpus is ever
committed.

**The general lesson for anyone building an eval:** an agent's blast radius is
its *project root*, not its working directory. Putting the harness and the
workspace in one tree is enough to break isolation, and the failure mode is a
better-looking number.

---

## 8. The scope gate aborts headless runs having done no work

**Severity: high for any batch harness — it is a large, silent confound.**

A plan of more than five steps triggers scope review. A headless run has nobody
to approve it, so the turn aborts before executing anything:

```
status = error, model_calls = 2, cost = $0.00011, wall = 3.3s
"scope review is required for this plan, but the run is headless without an
 approval bypass — re-run interactively or enable the scope-review bypass"
```

The workspace is untouched, so the task scores as a clean failure and is
indistinguishable in the results from an agent that tried and got it wrong.
Left unaddressed, resolution accuracy would substantially be measuring *how
often the planner emitted more than five steps* rather than whether the agent
could do the task — and any arm that changed planning verbosity would move the
headline metric for a reason that has nothing to do with knowledge.

`headless_scope_bypass: "on"` under `agent_engine_config` disables the gate; the
documented condition for using it is a disposable working tree, which is
exactly what every trial here has. It is set, and recorded in the pinned config
so a reader knows which regime the series ran in.

Worth noting the gate's threshold is *five steps*, which is low enough that
ordinary multi-file tasks cross it routinely. Anyone running Stella
non-interactively at all — CI, batch, cron — is likely losing runs to this
without noticing, because the failure looks like a normal unsuccessful turn.

---

## 9. Reflection records lessons only from turns that went wrong

Not a defect, but load-bearing for anyone designing experience curricula. The
reflection prompt is failure-oriented ("This turn FAILED… identify the root
cause and a durable lesson"). A turn that succeeds yields `recorded: 0`:

```
task passed: True   ->  reflection.recorded: 0, reflections.jsonl: 0 lines
task failed         ->  reflection.recorded: 2, reflections.jsonl: 2 lines
```

So an agent learns nothing from work it gets right. An experience pool composed
of tasks the agent reliably solves transfers nothing, however large it is —
which means experience-pool difficulty is a first-class experimental parameter,
not an incidental one.

---

## 10. Perfectly-delivered conventions did not help — and the "noise" did

> **PARTLY RETRACTED — see 10b.** The claim that the mined process notes helped
> was made without the arm that could test it. A noise-only arm was run
> afterwards and refutes it. The oracle result below stands; the explanation
> credited to the process notes does not.

The ceiling probe (`experiments/precision_probe.py`) hands the agent context in
the prompt, bypassing the lifecycle entirely — no store, no recall, no ranking.
It exists to separate *"the facts never arrive"* from *"the facts would not help
if they did"*. Three arms differing only in the block appended to the prompt,
144 trials, one pool digest (`f8a7dfe7`), one binary (0.5.60), $1.86:

| arm | task pass | check rate | model calls | stuck-loop aborts |
|---|---|---|---|---|
| control (nothing appended) | 0.792 | 0.950 | 51.5 | 8 |
| oracle (the 4 house conventions) | 0.688 | 0.926 | 36.6 | 4 |
| diluted (same 4 + 8 mined process notes) | **0.896** | **0.979** | 40.4 | **0** |

Paired over 12 tasks, bootstrap 95% CI:

```
oracle  - control   task pass  -0.104  [-0.208, +0.000]   —
diluted - oracle    task pass  +0.208  [+0.083, +0.354]   excludes 0
diluted - control   task pass  +0.104  [-0.021, +0.229]   —
```

Both hypotheses the probe was built to choose between are wrong. Perfect facts
did not help; and the mined process memories — the exact output dismissed in
this repo as "8 of 10 were agent self-critique, 0 captured a convention" — were
the arm that worked.

Two mechanisms are visible in the failures, and both are categorical rather than
marginal.

**The injected convention was over-applied.** Three trials failed with
`error: missing required argument: …` — on `--amount` for `interest` and
`sweep`, and `--journal` for `reconcile`. All three are in the oracle arm; there
are **zero** such failures in the 96 control and diluted trials. The fourth
oracle fact says handlers must call `validate.require(args, "field")` before
indexing. The agent applied it to arguments the task never specified — `sweep`
moves an entire balance, so there is no `--amount` to require — and turned a
correct implementation into a hard failure. Stating a convention perfectly is
not free: it is also an instruction to enforce it, including where it does not
belong.

**The process notes stopped the flailing.** Stuck-loop aborts run control 8,
oracle 4, diluted 0. Three of the eight "noise" memories are about exactly that
("when encountering a loop… pivot to a fundamentally different strategy"). The
dominant failure mode on this pool is not getting a convention wrong; it is
looping until the step cap. Context that addresses looping helps; context that
restates conventions the agent already follows does not.

That is also why oracle looks *worse* than control on completed runs alone
(0.714 vs 0.865): it is not noise, it is the over-application above.

### What this does to the roadmap

The premise behind anchoring recall to files and symbols was that better
retrieval precision would deliver the right conventions at the right moment.
This probe says the conventions were never the bottleneck **on this pool**, so
better delivery of them buys nothing here. That is an argument about
prioritization, not about the graph index being wrong.

### Limits, which are severe

- **Ceiling.** Control already scores 0.950 on checks, with 5 of 12 tasks at a
  clean 1.00. There is very little room to improve, and a probe with no headroom
  cannot see a positive effect even where one exists.
- **One check does nearly all the work.** Of the failing checks, `behaviour`
  accounts for 28 of 33; `registered`, `validated`, `minor_units` and
  `ledger_error` fail 0–1 times each across 144 trials. The rebuild bought ~5
  named checks per task, but on this pool four of them are saturated — so the
  effective instrument is still close to one bit, which is the thing the rebuild
  set out to fix.
- **Six contrasts were computed.** At α=0.05 the family-wise error rate is ~26%,
  and `diluted - oracle` is the only one excluding zero. Treat it as the one
  worth replicating, not as established.
- **No noise-only arm.** Facts+noise beat facts, but the design cannot say
  whether the eight process notes would beat *nothing*. That arm was cut for
  budget and is now the single highest-value follow-up — it is the difference
  between "process advice helps" and "diluting an over-forceful rule helps".
- **One run, k=4.** This repo's own headline effect has flipped sign three
  times.

### What follows

1. Add the **noise-only** arm. It is the missing cell of the 2×2 and it decides
   which mechanism above is real.
2. Raise task difficulty until control lands nearer 0.6 than 0.95. Five tasks at
   a clean 1.00 are contributing nothing but cost.
3. Make the conventions load-bearing in the tasks, or stop claiming the eval
   measures convention transfer. Right now a task can fail every convention
   check and still be rare enough not to matter.

---

## 10b. The noise-only arm refutes half of finding 10

Finding 10 credited the eight mined process notes with diluted's advantage, on
the strength of a stuck-loop count (control 8, oracle 4, diluted 0) and three of
those notes being about not looping. That inference had no arm behind it, and
finding 10 said so — "the design cannot say whether the eight process notes
would beat *nothing*". The missing cell was run. It does not.

Completing the 2×2 over {facts} × {process notes}, 192 trials, one digest, one
binary, $2.57 total:

| | no notes | notes |
|---|---|---|
| **no facts** | control 0.792 | noise 0.812 |
| **facts** | oracle 0.688 | diluted 0.896 |

```
noise   - control   task pass  +0.021  [-0.083, +0.125]   —
oracle  - control   task pass  -0.104  [-0.208, +0.000]   —
diluted - control   task pass  +0.104  [-0.021, +0.229]   —
diluted - oracle    task pass  +0.208  [+0.083, +0.354]   excludes 0
```

The process notes are **inert on their own**: noise lands on top of control on
both scales, and its stuck-loop count is 6 against control's 8 — not the 0 that
prompted the mechanism. Whatever produced diluted's clean loop record, it is not
"the notes teach the agent to stop looping", because the notes alone did not.

### What actually survives

Of six contrasts, exactly one excludes zero — `diluted - oracle` — and it is a
contrast **between two treatment arms, neither of which reliably beats
control**. Read together with `oracle - control` sitting at `[-0.208, +0.000]`,
the parsimonious account is not that any arm helped. It is that **oracle alone
hurt, and adding the notes cancelled the harm**. Diluted is not a gain over
doing nothing; it is a recovery from a self-inflicted loss.

The one mechanism that still has direct evidence is the over-application
signature, which is unchanged and remains categorical: three `missing required
argument` failures, all oracle, zero across the 144 control, noise and diluted
trials. Handing the agent a perfectly-stated rule is also handing it an
instruction to enforce that rule where it does not apply.

### The real blocker is the instrument, not the treatment

None of this can be resolved by more arms. Control already scores 0.950 on
checks with 5 of 12 tasks at a clean 1.00, so the largest improvement any
treatment could possibly show is ~0.05, and the noise-vs-control interval is
±0.03 wide. The probe cannot distinguish "no effect" from "an effect smaller
than the ceiling permits", and that is true of every question this pool is now
asked.

Two corrections to how this repo has been spending:

1. **Stop buying arms; buy headroom.** Tasks need to be hard enough that control
   lands near 0.6. Five tasks at 1.00 across all four arms contributed nothing
   but cost — roughly 40% of $2.57.
2. **Make the conventions decide outcomes, or stop calling this a convention
   eval.** `behaviour` accounts for 28 of 33 failing checks; `registered`,
   `validated`, `minor_units` and `ledger_error` fail 0–1 times each in 192
   trials. The four conventions the oracle block states are precisely the ones
   the agent already gets right unaided, which is why stating them can only do
   harm. A context experiment whose facts address a failure mode the tasks do
   not exhibit was never going to measure context.

The re-baselined series is deliberately **not** run. It would re-measure this
same saturated instrument at ~$17 for the current 22-task pool, and its control
arm cannot move.

---

## 11. Two attempts at raising difficulty failed. Arithmetic is the wrong lever.

Finding 10b's conclusion was that the instrument, not the treatment, was the
blocker: control scored 0.950 on checks with five of twelve tasks perfect in
every arm. The obvious response was to make the tasks harder. Two attempts, both
measured with a control-only calibration run before spending anything else:

| pool | task pass | check rate | tasks at 1.00 | cost |
|---|---|---|---|---|
| original (`f8a7dfe7`) | 0.792 | 0.950 | 5/12 | — |
| attempt 1 (`bf230f30`) | 0.771 | 0.938 | 8/12 | $0.48 |
| attempt 2 (`a01e7a21`) | 0.771 | 0.936 | 7/12 | $0.63 |

**Nothing moved.** 0.771 against an original 0.792, and at n=48 the standard
error is 0.061 — so the final number is indistinguishable from anything in
[0.65, 0.89]. Two iterations and $1.11 bought no measurable change.

### What was tried

**Attempt 1** — amounts whose naive parse is wrong (`int(float("1.15")*100)` is
114, not 115, while `money.parse_amount` returns 115), odd starting balances so
percentages leave a real fraction of a cent, and a second invocation on stateful
tasks so accumulation errors surface.

This *backfired*, and the reason is worth recording: each spec stated the exact
expected output, and for a computed field that string **is** the answer. Telling
the agent to print `collected 7.01 tax from alice` removes any need to work out
that 7% of 100.15 floors to 701 minor units. Tasks at a perfect score went
5/12 → 8/12. The pool got easier while it was being made harder.

**Attempt 2** — every worked example rewritten to use numbers that are not the
seeded case, so the format stays pinned exactly while the value must be
computed. Guarded by `test_a_prompt_never_states_the_seeded_answer`, which reads
each task's `setup.json` and refuses any prompt containing a rendered balance or
their total. That recovered ~2 points of check rate and no task pass at all.

### Why it did not work

The traps *do* fire when the answer is withheld — `eval-03-interest` fails with
`credited 500.75 interest to alice`, the float leaking straight into the output.
But they fire rarely, because the model reads the corpus, finds `money.py`, and
uses `parse_amount`. The four conventions are discoverable in about a minute of
reading, which is the same fact that made finding 10's oracle arm useless: you
cannot make knowledge valuable by testing it harder when it is already free.

Seven of twelve tasks remain at a clean 1.00. Four carry the entire signal —
`installments` 0.75, `reconcile` 0.83, `interest` 0.85, `share` 0.85 — and the
other eight buy nothing but cost.

### The calibration instrument is itself coarse

A 48-trial control run resolves to ±0.12 at 95%. It can tell 0.95 from 0.60; it
cannot tune difficulty finely, and it certainly cannot detect the ~2-point moves
these attempts produced. Anyone iterating on difficulty with this loop should
size the change to be obvious, or size the run to see it.

### What follows

Stop tuning arithmetic. Two measured failures are enough to call the lever wrong
for this model. The remaining options, in the order they seem worth trying:

1. **Change the difficulty axis** to something a single careful read cannot
   solve — a later command that must respect an earlier one's journal format, or
   state that must survive a sequence rather than an invocation.
2. **Prune the seven saturated tasks.** It will not lower control much, but
   roughly 60% of every run currently pays for trials that cannot move.
3. **Replace the pool with a harder one that still shares a codebase.**
   Heterogeneous benchmarks (Terminal-Bench and similar) buy headroom but cost
   the mechanism: the value of this design is that the transferable knowledge is
   a small enumerable set, which is what made "0 of 10 memories captured a
   convention that decided pass/fail" a computable statement. A harder *single
   repo* keeps that; a scattered pool does not.

The honest summary is that the ledger corpus may simply be too small a world to
contain knowledge worth remembering. That is a finding about the experiment's
design, and it was cheaper to learn from $1.11 of calibration than from a $17
series.

---

## 12. Correctness was the wrong outcome. Context works — on the other axes.

Findings 10–11 concluded that no arm beat control and that the instrument was
saturated. Both statements are true **of task pass rate**, and both are
incomplete, because pass/fail was the only outcome being scored. The same 192
trials, re-scored on effort and on how often the agent had to be steered:

| arm | task pass | model calls | cost | stuck-loops |
|---|---|---|---|---|
| control | 0.792 | 51.5 | $0.0147 | 8 |
| oracle (facts) | 0.688 | 36.6 | $0.0127 | 4 |
| noise (notes) | 0.812 | 45.4 | $0.0149 | 6 |
| diluted (both) | 0.896 | **40.4** | **$0.0113** | **0** |

Paired over 12 tasks, completed trials only (an abort truncates a run and would
flatter whichever arm aborts more):

```
model calls     diluted - control    -9.89  [-19.73, -0.29]   -25.1%   excludes 0
cost            diluted - control   -33.7%  [        , -0.00]           excludes 0
stuck-loop rate diluted - control    -0.17  [ -0.25, -0.08]  -100.0%   excludes 0
task pass       diluted - control    +0.10  [ -0.02, +0.23]            —
```

The arm that showed *no reliable correctness gain* used **a quarter fewer turns,
a third less money, and never once had to be steered** — control looped after a
steering warning 8 times in 48 trials; diluted, zero.

### The saturated tasks were not saturated

The claim in finding 11 that seven tasks "buy nothing but cost" was wrong. On the
five where control scores a perfect 1.00 on every check:

| task | control calls | diluted calls | Δ |
|---|---|---|---|
| eval-01-refund | 57.0 | 17.0 | −40.0 |
| eval-09-reconcile | 39.3 | 24.8 | −14.6 |
| eval-08-installments | 36.5 | 32.2 | −4.2 |
| eval-10-cap | 21.8 | 19.3 | −2.4 |
| eval-12-largest | 22.5 | 25.3 | +2.8 |
| **all five** | **35.2** | **23.9** | **−32.2%** |

Control's own spread on those tasks is sd=17.2 over a 19–93 range. A binary
outcome cannot see any of that. **Turns-to-solve does not saturate**: an agent
that always succeeds can still take 19 turns or 93.

This dissolves the headroom problem that finding 11 spent $1.11 failing to fix.
The tasks did not need to be harder. The outcome needed to be continuous.

### Which ingredient does what

The 2×2 separates them cleanly, and the account is mechanistic:

* **Facts drive efficiency.** oracle −21.7% calls, noise +5.4%. Knowing that
  handlers live in `registry.py` means not searching for them.
* **Facts alone drive harm.** The over-application signature from finding 10 —
  three `missing required argument` failures, all oracle, none elsewhere.
* **Notes alone do almost nothing** on any axis (finding 10b), but combined with
  facts they cancel the harm while the efficiency survives.

So "context did not help" was an artifact of measuring one dimension. Context
made the agent faster, cheaper and far less likely to need intervention, and
those effects are larger and cleaner than anything on the pass-rate axis.

### Limits

- Many contrasts have now been computed across findings 10–12; the family-wise
  error rate is high. What earns confidence here is not one interval but three
  independent measures (calls, cost, steering) agreeing in direction and size on
  the same arm.
- Fewer calls is only good if the work still gets done. It does: diluted has the
  *highest* pass rate and the *fewest* aborts, so it is finishing more often, not
  giving up sooner.
- One run. It needs replication before the sizes are trusted.
- These are one-shot headless trials, so "needed steering" is proxied by the
  harness's own stuck-loop warning rather than by a human intervening.

### What follows

1. **Make effort and steering first-class outcomes**, reported beside pass rate
   in every scoreboard, not dug out of failure diagnostics afterwards.
2. **Re-run the series on these axes.** The correctness verdict was
   underpowered; the effort verdict may not be, because the outcome is
   continuous and every trial contributes signal rather than one bit.
3. **Stop tuning task difficulty.** Finding 11's recommendation is withdrawn: the
   pool does not need to be harder, and the eight "wasted" tasks are carrying a
   large efficiency signal.

---

## 13. The store learns the right things, six times over — and they are the wrong things to learn

Read the treatment arm's actual memories after two rounds of `series-005`, and
two problems are visible at once. Neither is the one we had been looking for.

### It is no longer mining self-critique

22 of 23 lessons are domain facts about the codebase; exactly one is the agent
commenting on its own process. Finding 9 and the 8-in-10 self-critique
measurement that motivated so much of this work describe a system that no longer
exists — #768 fixed it.

### It stores six facts twenty-three times

| stored | fact |
|---|---|
| **7×** | commands are registered in `registry.py` |
| 4× | use `parse_amount` / `format_amount` |
| 4× | handlers live in `commands/` |
| 2× | validate arguments with `require()` |
| 2× | error handling |
| 1× | handler signature |

**61% of the store is restatement.** Byte-identical content already collapses —
a memory's lineage is seeded from its content hash — but the reflection loop
emits paraphrases, not copies, so near-duplicates accumulate without limit.

This is not untidiness. Recall has a budget. Three slots spent on three
phrasings of one fact are three slots not spent on the other five, so the store
gets *worse* at covering the codebase the longer it runs. The oracle arm that
cut steps 25% carried four **distinct** facts; the live store cannot reliably
deliver that spread.

Fixed in `stella` by `retain_unknown`, which applies the predicate
`retain_unforgotten` already used, pointed at live memories instead of
tombstones. The "is this the same lesson in different words" machinery existed
and had only ever been asked *did the user delete this*, never *do we know this
already*.

### The deeper problem: it is memorising the table of contents

Every fact above is one file-read away. `registry.py` is one file. `money.py` is
one file. `commands/` is one directory listing.

That is the same wall finding 11 hit from the other side — *knowledge that is
free to acquire cannot be made valuable by testing it harder* — and it explains
finding 10's oracle arm, which delivered those exact conventions perfectly and
did not help. A memory is worth its recall slot only in proportion to what it
costs to rediscover, and these cost a minute of reading.

Deduplication is still worth doing; a store that is 61% restatement is broken on
its own terms. But **six perfectly deduplicated facts about `registry.py` will
not help either.** It would be a tidier store of worthless memories.

The categories that would pay are the ones absent from the code: gotchas that
cannot be read anywhere ("this test is flaky"), decisions and the reasoning
behind them, and user preferences. None can be re-derived at any price.

### What this means for the experiment itself

The corpus is a toy ledger: four conventions, all written down in one
`CONTRIBUTING.md`, no history, no flakiness, no prior decisions, no user. **It
contains nothing in the categories that make memory pay.**

So the proving ground may be structurally incapable of demonstrating memory
working, however well the memory system behaves — not because the tasks are too
easy (finding 11 tested and rejected that), but because the *world* is too
small to hold knowledge worth remembering. That is a claim about the
experiment's design, and it is the most important thing on this page.
