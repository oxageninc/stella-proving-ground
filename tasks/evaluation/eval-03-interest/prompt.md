Add a `interest` command to the ledgerctl CLI in this repository.

`ledgerctl interest --account alice --rate 5` credits 5 percent of the current balance.
It prints `credited <amount> interest to <account>` — crediting 2.00 prints exactly
`credited 2.00 interest to alice`. Any fraction of a cent is discarded (round down), and
interest compounds: a second call charges the rate against the new balance.
Record a journal entry with `"type": "interest"`. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
