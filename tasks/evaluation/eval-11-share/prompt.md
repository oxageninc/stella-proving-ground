Add a `share` command to the ledgerctl CLI in this repository.

`ledgerctl share --account alice` prints the account's share of all money as a whole-number
percentage, rounded down, as exactly `alice holds 79% of 125.52`.
A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
