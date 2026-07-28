Add a `close` command to the ledgerctl CLI in this repository.

`ledgerctl close --account bob` removes an account and prints exactly `closed bob`.
Closing an account with a non-zero balance must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
