Add a `tax` command to the ledgerctl CLI in this repository.

`ledgerctl tax --account alice --rate 7` debits 7 percent of the balance as tax.
It prints `collected <amount> tax from <account>` — collecting 2.00 prints exactly
`collected 2.00 tax from alice`. Any fraction of a cent is discarded (round down), and a
second call taxes the reduced balance. Record a journal entry with `"type": "tax"`.
A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
