Add a `fee` command to the ledgerctl CLI in this repository.

`ledgerctl fee --account alice --amount 2.01` debits a service fee and prints exactly
`charged 2.01 fee to alice`. Record a journal entry with `"type": "fee"`.
A fee larger than the balance must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
