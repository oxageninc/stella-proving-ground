Add a `topup` command to the ledgerctl CLI in this repository.

`ledgerctl topup --account bob --amount 7.25` credits an account and prints
exactly `topped up bob by 7.25`. Record a journal entry with
`"type": "topup"`. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
