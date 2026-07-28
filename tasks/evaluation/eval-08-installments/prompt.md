Add a `installments` command to the ledgerctl CLI in this repository.

`ledgerctl installments --account bob --amount 2.30 --count 3` divides the amount into
that many parts as evenly as possible in minor units, giving any remainder to the FIRST
installment. It prints `<count> installments of <a>, <b>, ...` — dividing 1.01 into 2 prints
exactly `2 installments of 0.51, 0.50`. It changes no balance.
A count of zero must fail cleanly.

Read the repository first — it has house conventions that the test suite
enforces. Do not add dependencies. Do not modify the test suite.
