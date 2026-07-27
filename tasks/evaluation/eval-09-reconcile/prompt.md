Add a `reconcile` command to the ledgerctl CLI in this repository.

`ledgerctl reconcile` sums every journal entry's `amount` and prints exactly
`journal 1.75 across 3 entries` for a ledger whose entries total 175 minor units.
An entry without an `amount` counts toward the entry total but adds nothing to the sum.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
