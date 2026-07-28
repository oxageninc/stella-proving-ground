# Self-improvement status update — 2026-07-27, 12:02 PDT

Written in plain language, on purpose. No statistics vocabulary is assumed. If a
term has to be technical, it is explained the first time it appears.

---

## 1. The question we are actually trying to answer

Stella has a memory. As it works, it writes down lessons ("reflection"), stores
them, and later pulls relevant ones back into its prompt ("recall").

The claim we want to test is simple:

> **Does an agent that has done work before get better at new work, because of
> what it remembered?**

That is what "self-improvement" means here. Not "does it feel smarter" — does
its measured success rate go up.

## 2. How the experiment is set up

We built a small fake codebase: a command-line ledger tool (`ledgerctl`) that
tracks money in accounts. It has four house rules baked into it — for example,
"every new command must be listed in a registry file, or it is unreachable," and
"money is always whole cents as integers, never decimals."

Then we have two piles of tasks:

- **Experience tasks** — work the agent does *to build up memories*.
- **Evaluation tasks** — work we *score it on*. It never learns from these.

Each evaluation task is graded by a program (a "verifier") that actually runs the
agent's code and checks it. There is no model judging another model.

We run the same thing several ways at once. Each way is called an **arm**:

- **treatment** — the agent has its memory from the experience tasks.
- **control** — the agent starts cold, no memory.
- **sham** — the agent gets *someone else's* irrelevant memories. This catches
  the boring explanation where any extra text in the prompt changes behaviour.

If memory works, treatment beats control, and sham does not.

A full run across all of that is called a **series**.

## 3. Where we are: the short version

**Self-improvement is not showing up.** Three separate series have found no
reliable benefit from accumulated memory.

But — and this is the important part — **we recently proved that our measuring
device could not have detected the effect even if it were there.** So the honest
statement is not "memory doesn't work." It is:

> We have been unable to measure it, and we now understand why.

## 4. What we found out today

### 4a. We handed the agent perfect notes. It got *worse*.

Rather than keep testing the whole memory pipeline (write → store → retrieve →
inject), we ran a shortcut experiment called a **probe**. We skipped the memory
system entirely and just *typed the four house rules directly into the prompt*,
perfectly worded. If perfect facts don't help, then improving how facts get
stored and retrieved is pointless — the premise would be wrong.

We ran four versions, 192 total runs, for $2.57:

| what the agent was given | how often it fully succeeded |
|---|---|
| nothing (control) | 79% |
| the 4 house rules only | **69%** |
| 8 real mined "process notes" only | 81% |
| both the rules and the notes | 90% |

**Giving it the perfect rules made it worse than giving it nothing.**

We found out why, and it is concrete rather than mysterious. Three runs failed
with the error `missing required argument`. All three were in the
perfect-rules group; there were **zero** such failures in the other 144 runs.

One of the four house rules says handlers must check that required arguments are
present. The agent read that, believed it, and then enforced it on commands that
*have no such argument*. For example, the `sweep` command moves an account's
entire balance — there is no amount to supply — and the agent demanded one
anyway, turning working code into a hard failure.

**Lesson: stating a rule perfectly is also an instruction to apply it
everywhere, including where it does not belong.** That is a real finding about
injecting context, and it survived every later check.

### 4b. I got the next part wrong, and had to correct it publicly

Looking at that table, I concluded the 8 "process notes" were the useful
ingredient, and wrote that up. The reasoning looked good: the group with notes
never got stuck in a loop, while the control group got stuck 8 times, and three
of the notes are literally about not looping.

**That was wrong, and I had not run the test that could tell.** I flagged the gap
in the write-up, then ran the missing group — notes only, no rules. It landed at
81%, statistically indistinguishable from the 79% of getting nothing. And it got
stuck in a loop 6 times, not zero.

So the notes do nothing on their own. The write-up is now marked partly
retracted (see finding 10b in `FINDINGS.md`).

The corrected reading is duller and more honest: **no version reliably beat doing
nothing.** The one difference that held up was between two treatment groups, not
against the baseline. The simplest account is that the perfect rules hurt, and
adding the notes cancelled that harm — a recovery, not a gain.

### 4c. The real problem: the test is too easy

This is the finding that matters most, and it explains everything above.

The agent already scores **95%** on our grading checks with no help at all. Five
of our twelve evaluation tasks come back **perfect every single time, in all four
groups**.

You cannot measure an improvement on a task the agent already aces. There is
nowhere for the score to go. The most any help could possibly add is about 5
points, and our measurement uncertainty is already about 3 points wide. We are
trying to weigh a feather on a bathroom scale.

It gets worse when you look at *which* checks fail. Each task is graded on about
five separate named checks. Of all the failures across 192 runs:

- **28 of 33 failures** were the `behaviour` check — did the command produce the
  right output and the right numbers.
- The four *house-rule* checks failed **0 or 1 times each**, total.

So the four rules we were injecting are precisely the four things the agent
**already gets right without being told**. That is why telling it could only
hurt. We built an experiment about conventions, on tasks where conventions never
decide the outcome.

We rebuilt this evaluation earlier today specifically to get finer-grained
scoring — five checks per task instead of one pass/fail bit. That was the right
move, but four of the five checks turn out to be saturated, so in practice we are
still close to one bit of information per task.

## 5. What else got fixed today

**The build system could never have run.** `make build` and `make series` had
never worked on this Mac, not once. Apple ships a 2006 version of `make` that
silently ignores a feature the file depends on, so those commands were being read
as broken fragments. It went unnoticed for two reasons: the one command people
did run (`make smoke`) happened to avoid the feature, and every recipe ended in a
pipe, which reports the *pipe's* success rather than the command's — so a build
that died immediately still reported success. Now moved into ordinary shell
scripts. While moving it, found the cost estimate was hardcoded to 6 tasks when
the pool has 22, so it was quoting about a quarter of the true price.

**Memory anchors shipped** (stella PR #777, all checks passing). Memories now
link to the files they are about, so "what do we know about `registry.py`" is a
direct lookup instead of a fuzzy text-similarity guess. When a file is deleted,
the link is marked as no-longer-true without calling the memory *wrong* — because
it was not wrong, the world changed. Critically, this included wiring the search
path to actually respect that; without it, the previous work in this area had no
effect on anything the agent ever saw.

## 6. Money

- Credit remaining: **$4.10**.
- Today's probe: **$2.57** for 192 runs.
- Roughly **40%** of that was spent on tasks that returned a perfect score in
  every group — money spent learning nothing.
- A full re-run of the main series would cost about **$17** on the current task
  pool.

## 7. What I am doing next, and why

**I am not re-running the main series.** It was on the plan, and I am
deliberately skipping it. It would cost ~$17 to re-measure the same too-easy
test, against a baseline that cannot move. That is buying a number we already
know we cannot trust.

**Instead: make the tasks harder.** This costs no model credit to design, and it
is the thing blocking every other question. Two specific goals:

1. **Bring the baseline score down from ~95% to around 60%**, so there is room to
   detect an improvement.
2. **Make the house rules actually decide whether a task passes.** Right now a
   task can violate a convention and still pass, because the grading barely
   depends on conventions. For example: use amounts where doing the arithmetic
   with decimals instead of whole cents produces a visibly wrong answer, so the
   "money is integer cents" rule stops being decoration and starts being the
   difference between right and wrong.

**Then I will measure the new difficulty cheaply before trusting it** — one
baseline-only run, roughly $0.50, to confirm the score actually landed near 60%
rather than accidentally at 20% (unusably hard) or still at 90%. Guessing at
difficulty without checking is the exact mistake this project keeps making, and
it is cheap to avoid.

Only after that is it worth spending real money on the memory question again.

## 8. The one-paragraph summary

We still have no evidence that Stella gets better from its own memory. But today
we established that our test could not have shown it either way, because the
agent already passes almost everything and the specific facts we were testing are
things it already knows. We also learned something genuinely useful and slightly
counterintuitive: injecting perfect, correct context can make an agent *worse*,
because a clearly-stated rule reads as an order to apply it everywhere. Next step
is to make the test hard enough to be capable of showing a result, and to verify
that cheaply before spending anything further.
