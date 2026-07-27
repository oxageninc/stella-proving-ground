Add a `statement` command to the ledgerctl CLI in this repository.

`ledgerctl statement --account alice` prints the account's balance and how
many journal entries mention it, as exactly `alice 100.00 (2 entries)` for a
ledger where two entries reference alice. An entry mentions an account if any
of its values equals the account name. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
