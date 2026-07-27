Add a `share` command to the ledgerctl CLI in this repository.

`ledgerctl share --account alice` prints the account's share of the total held across ALL
accounts, as a whole-number percentage rounded down: `<account> holds <p>% of <total>`.
An account holding 1.00 of a 4.00 total prints exactly `alice holds 25% of 4.00`.
A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
