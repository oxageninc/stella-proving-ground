Add a `statement` command to the ledgerctl CLI in this repository.

`ledgerctl statement --account alice` prints the balance and how many journal entries
mention it, as `<account> <balance> (<n> entries)` — an account holding 3.50 named in 4
entries prints exactly `alice 3.50 (4 entries)`. An entry mentions an account if any of its
values equals the account name. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
