Add a `cap` command to the ledgerctl CLI in this repository.

`ledgerctl cap --account alice --max 50.00` reduces a balance to the cap when it exceeds it,
records a journal entry with `"type": "cap"` whose `amount` is the amount removed, and prints
exactly `capped alice at 50.00, removed 50.15`. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
