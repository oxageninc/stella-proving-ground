Add a `open` command to the ledgerctl CLI in this repository.

`ledgerctl open --account carol` creates a new account with a zero balance and
prints exactly `opened carol`. Opening an account that already exists must
fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
