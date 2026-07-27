Add a `tax` command to the ledgerctl CLI in this repository.

`ledgerctl tax --account alice --rate 7` debits 7 percent of the balance as tax and prints
exactly `collected 7.00 tax from alice`. Record a journal entry with `"type": "tax"`.
Any fraction of a cent is discarded (round down). A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
