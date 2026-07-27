Add a `withdraw` command to the ledgerctl CLI in this repository.

`ledgerctl withdraw --account alice --amount 5.00` debits the account and prints exactly
`withdrew 5.00 from alice`. Record a journal entry with `"type": "withdraw"`.
Withdrawing more than the balance must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
