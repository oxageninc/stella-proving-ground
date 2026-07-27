Add a `zero` command to the ledgerctl CLI in this repository.

`ledgerctl zero --account alice` sets an account balance to zero and prints
exactly `zeroed alice`. Record a journal entry with `"type": "zero"` whose
`amount` is the balance that was removed. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
