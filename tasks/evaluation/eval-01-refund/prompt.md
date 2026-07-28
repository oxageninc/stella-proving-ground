Add a `refund` command to the ledgerctl CLI in this repository.

`ledgerctl refund --account alice --amount 1.15` debits the account and prints exactly
`refunded 1.15 from alice`. Record a journal entry with `"type": "refund"`.
Refunding more than the balance must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
