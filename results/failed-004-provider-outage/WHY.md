# series-004 — discarded, provider outage again

119 of a planned 990 trials, $0.53. **Forty-four have zero model calls**, the
same dead-socket signature as `failed-003`. Not scoreable, kept as evidence.

Two things this run establishes, both worth more than the trials themselves:

**The guard works.** `failed-003` ran 500 trials past a dead provider and exited
0. This one stopped at 119 — `health.provider_outage` saw the 12-trial dead
streak and pulled the run. That is the fix doing exactly its job on the very
next occurrence.

**The harness is not the only thing that can die.** This run also lost its
supervising agent to `ENOTFOUND` when the machine slept. Local runs do not
survive a closed laptop, and the credits endpoint keeps answering while
inference is dead — so "the API is up" is not evidence that trials are running.
Test the inference path, not reachability.
