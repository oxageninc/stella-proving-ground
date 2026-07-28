Add a `sweep` command to the ledgerctl CLI in this repository.

`ledgerctl sweep --from alice --to bob` moves the entire balance of one account into
another, leaving the source at zero. It prints `swept <amount> from <source> to <target>` —
sweeping a source that holds 3.50 prints exactly `swept 3.50 from alice to bob`.
Record a journal entry with `"type": "sweep"`. A missing account must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
