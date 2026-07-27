Add a `interest` command to the ledgerctl CLI in this repository.

`ledgerctl interest --account alice --rate 5` credits 5 percent of the current balance and
prints exactly `credited 5.00 interest to alice` the first time. Record a journal entry with
`"type": "interest"`. Any fraction of a cent is discarded (round down), and interest
compounds — a second call charges 5 percent of the new balance.
A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
