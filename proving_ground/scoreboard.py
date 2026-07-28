"""Generate the scoreboard from raw results.

Every metric, per epoch, per arm — including the ones that went the wrong way.
The scoreboard reads only `results.jsonl`, so it can re-score an old series
when the methodology changes without re-running a single model call.
"""

from __future__ import annotations

from pathlib import Path

from .stats import (
    CONTINUOUS_OUTCOMES,
    CONTRAST_PAIRS,
    EFFORT_OUTCOMES,
    MIN_MEANINGFUL_EFFECT,
    STEERING_OUTCOME,
    family_wise_error,
    load_results,
    paired,
    paired_outcome,
    regression_rate,
    summarize,
    trend,
    verdict,
)


def _fmt(x: float, spec: str = ".3f") -> str:
    if x != x:  # NaN
        return "—"
    return format(x, spec)


def render(results_path: Path) -> str:
    rows = load_results(results_path)
    summary = summarize(rows)
    if not summary:
        return "# Scoreboard\n\nNo evaluation trials recorded.\n"

    arms = sorted({a for (a, _) in summary})
    epochs = sorted({e for (_, e) in summary})
    config = rows[0].get("config", {})

    out: list[str] = []
    out.append("# Scoreboard\n")
    out.append(
        f"Series pinned to `{config.get('model')}` via `{config.get('provider')}`, "
        f"Stella `{config.get('stella_version')}` "
        f"(`{str(config.get('stella_commit'))[:12]}`), "
        f"task pool `{config.get('task_pool_digest')}`.\n"
    )
    out.append(
        f"Evaluation pool is held out: it is measured and never learned from. "
        f"Primary metric is resolution accuracy against a deterministic "
        f"verifier. Pre-registered threshold for a result: "
        f"**{MIN_MEANINGFUL_EFFECT:.0%}** absolute, paired, CI excluding zero.\n"
    )
    out.append(
        "Reported beside it, and **exploratory rather than pre-registered**: "
        "effort per trial and how often the agent had to be steered. Finding 12 "
        "showed pass rate saturating on this pool while effort did not — an "
        "agent that always succeeds can still take 19 turns or 93 — so a "
        "scoreboard that reads only the accuracy row is blind to most of the "
        "signal it paid for.\n"
    )

    v = verdict(summary)
    cont = v.get("continuous") or {}
    out.append("\n## Verdict\n")
    out.append(f"**Accuracy (pre-registered): the claim is {v['claim']}.** {v['reason']}.\n")
    if cont.get("claim"):
        out.append(
            f"\n**Effort and steering (exploratory): {cont['claim']}.** "
            f"Detail in *Effort* and *Steering* below.\n"
        )
    if v.get("treatment_minus_control"):
        tc, ts = v["treatment_minus_control"], v.get("treatment_minus_sham")
        out.append(
            f"At the final epoch (E{v['final_epoch']}), treatment − control = "
            f"{_fmt(tc['delta'], '+.3f')} (95% CI [{_fmt(tc['ci'][0], '+.3f')}, "
            f"{_fmt(tc['ci'][1], '+.3f')}])"
            + (
                f"; treatment − sham = {_fmt(ts['delta'], '+.3f')} "
                f"(95% CI [{_fmt(ts['ci'][0], '+.3f')}, {_fmt(ts['ci'][1], '+.3f')}])."
                if ts else "."
            )
        )
        out.append(
            f"\nTreatment moved {_fmt(v['treatment_trend'], '+.3f')} across the "
            f"series against a control arm that drifted {_fmt(v['control_drift'], '.3f')} "
            f"on its own — treatment "
            f"{'clears' if v['treatment_clears_control_drift'] else 'does not clear'} "
            f"control's own run-to-run movement. Treatment regression rate: "
            f"{_fmt(v['regression_rate'])} "
            f"({v['regressed_task_instances']} task-epochs lost).\n"
        )
        null = v.get("control_null") or {}
        if null.get("replications", 0) >= 2:
            out.append(
                f"\n**Empirical null.** The control arm does no experience work "
                f"and is wiped before every evaluation, so its "
                f"{null['replications']} epochs are the same experiment repeated. "
                f"It ranged {_fmt(null['range'], '.3f')} "
                f"(sd {_fmt(null['spread'], '.3f')}) across them, with nothing "
                f"changed. Any effect smaller than that band is not "
                f"distinguishable from nothing."
            )
            if v.get("underpowered"):
                out.append(
                    f"\n> **This series is underpowered for its own threshold.** "
                    f"Control's no-op range ({_fmt(null['range'], '.3f')}) exceeds "
                    f"the pre-registered {MIN_MEANINGFUL_EFFECT:.0%} effect size, so a "
                    f"true effect at exactly that size could not be resolved here. "
                    f"Reported rather than adjusted after the fact: the fix is more "
                    f"evaluation tasks, not a friendlier threshold.\n"
                )

    out.append("\n## Resolution accuracy (primary)\n")
    out.append("Mean per-task pass rate, with a 95% bootstrap CI over tasks.\n")
    header = "| arm | " + " | ".join(f"E{e}" for e in epochs) + " |"
    out.append(header)
    out.append("|---|" + "---|" * len(epochs))
    for arm in arms:
        cells = []
        for e in epochs:
            s = summary.get((arm, e))
            cells.append(
                f"{_fmt(s.accuracy)} [{_fmt(s.accuracy_lo)}, {_fmt(s.accuracy_hi)}]"
                if s
                else "—"
            )
        out.append(f"| **{arm}** | " + " | ".join(cells) + " |")

    out.append("\n## Effort per trial (completed trials only)\n")
    out.append(
        "What the answer cost, per trial — **not** per solved task. The "
        "`*_per_solved` tables further down divide by the number of passes, so "
        "they move when accuracy moves and read as an efficiency change that "
        "never happened. These are the raw per-trial means.\n\n"
        "Restricted to trials with `status == completed`. An abort truncates a "
        "run, so a trial that gave up at step 12 records less effort than one "
        "that worked honestly to step 60 — including aborts would reward "
        "whichever arm quits more. The arms differ on abort rate, and that is "
        "reported separately under *Instrument health* rather than smuggled in "
        "here.\n"
    )
    for o in EFFORT_OUTCOMES:
        out.append(f"\n**{o.label}** — lower is better\n")
        out.append("| arm | " + " | ".join(f"E{e}" for e in epochs) + " |")
        out.append("|---|" + "---|" * len(epochs))
        for arm in arms:
            cells = []
            for e in epochs:
                s = summary.get((arm, e))
                cells.append(
                    _fmt(s.outcome_mean.get(o.key, float("nan")), o.fmt) if s else "—"
                )
            out.append(f"| {arm} | " + " | ".join(cells) + " |")

    out.append("\n### Trials contributing to the effort numbers\n")
    out.append(
        "`completed / total`. An effort mean resting on a handful of surviving "
        "trials is not the same measurement as one resting on all of them.\n"
    )
    out.append("| arm | " + " | ".join(f"E{e}" for e in epochs) + " |")
    out.append("|---|" + "---|" * len(epochs))
    for arm in arms:
        cells = []
        for e in epochs:
            s = summary.get((arm, e))
            cells.append(f"{s.completed}/{s.trials}" if s else "—")
        out.append(f"| {arm} | " + " | ".join(cells) + " |")

    out.append(f"\n## Steering — {STEERING_OUTCOME.label} (all trials)\n")
    out.append(
        "Share of trials whose run ended with the harness's own *stuck-loop* "
        "warning: the agent was told it was looping and looped anyway. These "
        "are one-shot headless trials, so nobody is there to intervene — this "
        "is the closest proxy the design has for *a human had to step in*.\n\n"
        "Scored over **all** trials, unlike effort. Looping is only observable "
        "on runs that went wrong, so filtering to completed trials would define "
        "the outcome out of existence.\n"
    )
    out.append("| arm | " + " | ".join(f"E{e}" for e in epochs) + " |")
    out.append("|---|" + "---|" * len(epochs))
    for arm in arms:
        cells = []
        for e in epochs:
            s = summary.get((arm, e))
            cells.append(
                _fmt(s.outcome_mean.get(STEERING_OUTCOME.key, float("nan")), ".3f")
                if s else "—"
            )
        out.append(f"| {arm} | " + " | ".join(cells) + " |")

    out.append("\n## Paired contrasts on effort and steering\n")
    out.append(
        "Same task, same epoch, arm minus arm, bootstrapped over tasks — the "
        "identical machinery the accuracy contrast uses. Negative favours the "
        "first arm on every row: these outcomes are all costs.\n\n"
        "`rel` is the delta as a share of the second arm's mean over the same "
        "shared tasks. No threshold is applied: none was pre-registered for "
        "these axes, and choosing one now, after seeing the probe, would be "
        "choosing it knowing the answer.\n"
    )
    out.append("| epoch | comparison | outcome | delta | 95% CI | rel | n tasks | verdict |")
    out.append("|---|---|---|---|---|---|---|---|")
    n_continuous = 0
    for e in epochs:
        for a, b in CONTRAST_PAIRS:
            for o in CONTINUOUS_OUTCOMES:
                c = paired_outcome(summary, e, a, b, o.key)
                if not c:
                    continue
                n_continuous += 1
                rel = c.relative
                out.append(
                    f"| E{e} | {a} − {b} | {o.label} | {_fmt(c.delta, '+' + o.fmt)} | "
                    f"[{_fmt(c.lo, '+' + o.fmt)}, {_fmt(c.hi, '+' + o.fmt)}] | "
                    f"{('—' if rel != rel else format(rel, '+.1%'))} | {c.n_tasks} | "
                    f"{c.verdict()} |"
                )

    n_accuracy = sum(
        1 for e in epochs for a, b in CONTRAST_PAIRS if paired(summary, e, a, b)
    )
    total = n_accuracy + n_continuous
    out.append(
        f"\n> **{total} contrasts are computed on this page** "
        f"({n_accuracy} on accuracy, {n_continuous} on effort and steering). At "
        f"alpha = 0.05 the family-wise error rate is "
        f"**~{family_wise_error(total):.0%}** — several intervals excluding zero "
        f"by chance alone is the expectation, not the exception. More contrasts "
        f"have already been run across findings 10–12, so the true family is "
        f"larger than this page. What earns confidence is not one interval but "
        f"independent measures agreeing in direction and size on the same arm, "
        f"and then replicating. Read this table that way.\n"
    )

    out.append("\n## Store growth\n")
    out.append(
        "Memories carried into each epoch's evaluation. The sham arm must stay "
        "comparable to treatment or it is no control at all.\n"
    )
    out.append("| arm | " + " | ".join(f"E{e}" for e in epochs) + " |")
    out.append("|---|" + "---|" * len(epochs))
    for arm in arms:
        cells = [
            str(summary[(arm, e)].store_memories) if (arm, e) in summary else "—"
            for e in epochs
        ]
        out.append(f"| {arm} | " + " | ".join(cells) + " |")

    out.append("\n## Per-solved-task ratios (kept for continuity — read with care)\n")
    out.append(
        "These divide total effort by the number of *passes*, so they conflate "
        "effort with correctness: an arm that solves one more task looks more "
        "efficient without having changed how it works. The per-trial tables "
        "above are the ones to read for effort. Retained because series 001 and "
        "002 were published on them.\n"
    )
    for title, attr, spec in (
        ("Token efficiency — tokens per solved task", "tokens_per_solved", ".0f"),
        ("Cost — USD per solved task", "cost_per_solved", ".4f"),
        ("Speed — seconds per solved task", "seconds_per_solved", ".1f"),
        ("Speed — model calls per solved task", "calls_per_solved", ".2f"),
        ("Context efficiency — recalled tokens per model call", "recalled_tokens_per_call", ".1f"),
        ("Context efficiency — share of recalled frames cited", "cited_share", ".3f"),
    ):
        out.append(f"\n## {title}\n")
        out.append("| arm | " + " | ".join(f"E{e}" for e in epochs) + " |")
        out.append("|---|" + "---|" * len(epochs))
        for arm in arms:
            cells = []
            for e in epochs:
                s = summary.get((arm, e))
                cells.append(_fmt(getattr(s, attr), spec) if s else "—")
            out.append(f"| {arm} | " + " | ".join(cells) + " |")

    out.append("\n## Memorization check — worked tasks vs. held-out tasks\n")
    out.append(
        "The evaluation pool is never worked, so it can only show transfer. The "
        "experience pool *is* worked, so it can show memorization. Improvement "
        "that appears on worked tasks and not on held-out ones is memorization, "
        "correctly named — and a context system is supposed to memorize, so "
        "seeing it here is expected rather than damning. The divergence between "
        "the two columns is the measurement.\n"
    )
    out.append("| arm | epoch | worked-task pass rate | held-out pass rate | divergence |")
    out.append("|---|---|---|---|---|")
    exp_rows = [r for r in rows if r.get("pool") == "experience"]
    for arm in arms:
        for e in epochs:
            worked = [r for r in exp_rows if r["arm"] == arm and r["epoch"] == e]
            held = [
                r for r in rows
                if r.get("pool") == "evaluation" and r["arm"] == arm and r["epoch"] == e
            ]
            if not worked and not held:
                continue
            wr = (sum(1 for r in worked if r["passed"]) / len(worked)) if worked else float("nan")
            hr = (sum(1 for r in held if r["passed"]) / len(held)) if held else float("nan")
            div = wr - hr if worked and held else float("nan")
            out.append(
                f"| {arm} | E{e} | {_fmt(wr)} (n={len(worked)}) | "
                f"{_fmt(hr)} (n={len(held)}) | {_fmt(div, '+.3f')} |"
            )

    out.append("\n## Instrument health\n")
    out.append(
        "Degenerate trials — ones that produced no work at all — are reported "
        "separately, because they fail identically to an agent that tried and "
        "got it wrong. A null result caused by aborted runs is not a null "
        "result about the lifecycle.\n"
    )
    out.append("| arm | epoch | trials | zero-work | non-completed status | mean calls |")
    out.append("|---|---|---|---|---|---|")
    eval_rows = [r for r in rows if r.get("pool") == "evaluation"]
    for arm in arms:
        for e in epochs:
            trials = [r for r in eval_rows if r["arm"] == arm and r["epoch"] == e]
            if not trials:
                continue
            zero = sum(1 for t in trials if t.get("model_calls", 0) <= 2)
            bad = sum(1 for t in trials if t.get("status") not in ("completed", ""))
            calls = sum(t.get("model_calls", 0) for t in trials) / len(trials)
            out.append(
                f"| {arm} | E{e} | {len(trials)} | {zero} | {bad} | {calls:.1f} |"
            )

    out.append("\n## Regression rate\n")
    out.append(
        "Tasks solved at epoch *N* that fail at *N+1*. A system can learn "
        "net-positive while silently breaking what it used to get right.\n"
    )
    out.append("| arm | transition | solved before | regressed | rate | tasks |")
    out.append("|---|---|---|---|---|---|")
    for arm in arms:
        for r in regression_rate(summary, arm):
            out.append(
                f"| {arm} | E{r['from_epoch']}→E{r['to_epoch']} | "
                f"{r['solved_before']} | {r['regressed']} | {_fmt(r['rate'])} | "
                f"{', '.join(r['tasks']) or '—'} |"
            )

    out.append("\n## Paired comparisons — accuracy (primary)\n")
    out.append(
        "Same task, same epoch, arm minus arm. Pairing on task has far more "
        "power than comparing pool means.\n"
    )
    out.append("| epoch | comparison | delta | 95% CI | verdict |")
    out.append("|---|---|---|---|---|")
    for e in epochs:
        for a, b in CONTRAST_PAIRS:
            c = paired(summary, e, a, b)
            if c:
                out.append(
                    f"| E{e} | {a} − {b} | {_fmt(c.delta, '+.3f')} | "
                    f"[{_fmt(c.lo, '+.3f')}, {_fmt(c.hi, '+.3f')}] | {c.verdict()} |"
                )

    out.append("\n## Trend across the series\n")
    out.append("| arm | first | last | delta |")
    out.append("|---|---|---|---|")
    for arm in arms:
        t = trend(summary, arm)
        out.append(
            f"| {arm} | {_fmt(t.get('first', float('nan')))} | "
            f"{_fmt(t.get('last', float('nan')))} | {_fmt(t['delta'], '+.3f')} |"
        )

    out.append("\n## Per-task detail\n")
    out.append("Pass rate over k trials. Published in full, losses included.\n")
    tasks = sorted({t for s in summary.values() for t in s.per_task_rate})
    out.append("| task | " + " | ".join(f"{a} E{e}" for e in epochs for a in arms) + " |")
    out.append("|---|" + "---|" * (len(epochs) * len(arms)))
    for task in tasks:
        cells = []
        for e in epochs:
            for a in arms:
                s = summary.get((a, e))
                cells.append(_fmt(s.per_task_rate.get(task, float("nan")), ".2f") if s else "—")
        out.append(f"| `{task}` | " + " | ".join(cells) + " |")

    return "\n".join(out) + "\n"
