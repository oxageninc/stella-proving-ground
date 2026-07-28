Add a `split` command to the ledgerctl CLI in this repository.

`ledgerctl split --from alice --to bob,carol --amount 2.01` debits the source once and
divides the amount as evenly as possible across the comma-separated destinations, giving any
leftover minor units to the first. It prints exactly `split 2.01 from alice across 2 accounts`.
Record one journal entry with `"type": "split"`. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
