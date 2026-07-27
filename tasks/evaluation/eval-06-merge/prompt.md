Add a `merge` command to the ledgerctl CLI in this repository.

`ledgerctl merge --from bob --to alice` moves the source account's whole
balance into the destination, removes the source account, and prints exactly
`merged bob into alice`. Record a journal entry with `"type": "merge"`.
Merging a missing account, or an account into itself, must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
