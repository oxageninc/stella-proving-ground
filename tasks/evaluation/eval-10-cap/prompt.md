Add a `cap` command to the ledgerctl CLI in this repository.

`ledgerctl cap --account alice --max 50.00` reduces a balance to the cap when it exceeds it
and records a journal entry with `"type": "cap"` whose `amount` is the amount removed.
It prints `capped <account> at <max>, removed <amount>` — capping a 9.00 balance at 4.00
prints exactly `capped alice at 4.00, removed 5.00`. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
