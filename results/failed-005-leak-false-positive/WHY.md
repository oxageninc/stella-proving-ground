# series-005 — killed by the leakage gate, on a verb conjugation

380 of 990 attempts, $3.76, stopped at round 2 of 3. **No leak occurred.**

Five hits, all the same 4-gram, `records a journal entry`, all attributed to
`eval-10-cap`. The evaluation prompt says *"...and **records** a journal entry"*;
every experience prompt says *"**Record** a journal entry"*. One letter of verb
conjugation made the phrase evaluation-only, and an agent describing its own
work on an experience task — "the command records a journal entry" — tripped it.

All five excerpts are the agent talking about `fee`, `rename` and `zero`. Not one
mentions `cap`. There was nothing to find.

Fixed in `leakage.is_novel_word`, which now compares stems. Verified both ways:
the false positive is quiet, and the gate still fires on a whole leaked prompt,
on a single remembered output line, and on a leaked line from another task.

The rounds-1-and-2 data is not scoreable — the primary outcome is defined at the
final round, and round 3 never ran. Kept because the early split is still worth
seeing:

| steps to do the same work | round 1 | round 2 |
|---|---|---|
| no memory | 39.1 | 42.1 |
| with memory | 45.5 (+16%) | 43.2 (+3%) |
| useless memory | 41.2 (+5%) | 40.2 (-5%) |

Memory was *behind* in both rounds, with the deficit shrinking. Treat as a hint
about where to look, not a result.
