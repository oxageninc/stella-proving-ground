Add a `list` command to the ledgerctl CLI in this repository.

`ledgerctl list` prints every account name and formatted balance on one line, sorted by
name, joined by `, ` — a ledger of two accounts holding 3.50 and 1.25 prints exactly
`alice 3.50, bob 1.25`.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
