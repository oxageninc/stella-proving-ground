Add a `installments` command to the ledgerctl CLI in this repository.

`ledgerctl installments --account bob --amount 10.00 --count 3` divides the amount into 3
parts as evenly as possible in minor units, giving any remainder to the FIRST installment, and
prints exactly `3 installments of 3.34, 3.33, 3.33`. It changes no balance.
A count of zero must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
