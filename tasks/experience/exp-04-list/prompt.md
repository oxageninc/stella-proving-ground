Add a `list` command to the ledgerctl CLI in this repository.

`ledgerctl list` prints every account name and formatted balance on one line, sorted by
name, joined by `, ` — for the starting ledger exactly `alice 100.15, bob 25.37`.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
