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

## 3. Observations are never extracted on the `stella run` path

**Severity: high — the observe phase does not close automatically.**

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

## 6. The lifecycle loop does not close end-to-end on `main`

#755 opens by stating that the loop closes end to end (#469: observe → propose
→ govern → select → attribute → retire). On `main` at `ac5b344b`, the last two
phases are not present. `ContextUse` and `ContextUseFeedback` record kinds are
declared (`stella-core/src/context_record/kind.rs:28-29`) and their types
defined, but nothing outside tests constructs or appends them. Phase 4 (#715 —
efficacy attribution and reversible retirement) lives in an unmerged worktree.

Two consequences for the proving ground:

1. Attribution and retirement cannot be measured yet; only observe → propose →
   govern → select are live.
2. The regression-rate risk #755 attributes to Phase 4's retirement ("retiring
   the wrong record is exactly how you would see it") is **not yet live**. The
   metric is implemented and reported anyway, so that the baseline exists
   before retirement lands and the comparison is available the day it does.

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
