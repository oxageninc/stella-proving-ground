Add a `largest` command to the ledgerctl CLI in this repository.

`ledgerctl largest` prints the account with the highest balance as `<account> <balance>` —
for a top account holding 3.50 that is exactly `bob 3.50`. Ties break alphabetically.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
