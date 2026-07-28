Add a `reconcile` command to the ledgerctl CLI in this repository.

`ledgerctl reconcile` sums every journal entry's `amount` and prints
`journal <total> across <n> entries` — entries totalling 3.50 across 4 of them print exactly
`journal 3.50 across 4 entries`. An entry without an `amount` counts toward the entry total
but adds nothing to the sum.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
