"""Generate the scoreboard from raw results.

Every metric, per epoch, per arm — including the ones that went the wrong way.
The scoreboard reads only `results.jsonl`, so it can re-score an old series
when the methodology changes without re-running a single model call.
"""

from __future__ import annotations

from pathlib import Path

from .stats import (
    MIN_MEANINGFUL_EFFECT,
    load_results,
    paired,
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

    v = verdict(summary)
    out.append("\n## Verdict\n")
    out.append(f"**The claim is {v['claim']}.** {v['reason']}.\n")
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

    out.append("\n## Paired comparisons\n")
    out.append(
        "Same task, same epoch, arm minus arm. Pairing on task has far more "
        "power than comparing pool means.\n"
    )
    out.append("| epoch | comparison | delta | 95% CI | verdict |")
    out.append("|---|---|---|---|---|")
    for e in epochs:
        for a, b in (("treatment", "control"), ("treatment", "sham"), ("sham", "control")):
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
