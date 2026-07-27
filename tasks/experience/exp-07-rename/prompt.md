Add a `rename` command to the ledgerctl CLI in this repository.

`ledgerctl rename --from bob --to robert` renames an account, preserving its
balance, and prints exactly `renamed bob to robert`. Renaming a missing
account, or onto a name that already exists, must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
