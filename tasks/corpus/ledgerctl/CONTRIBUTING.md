# Contributing to ledgerctl

## Working here

Branch from `main`, keep commits focused, and run the suite before opening a
review. Type hints on public functions. Keep modules small.

## Review

Two approvals for anything touching persistence. One for everything else.
Reviewers will push back on code that does not match the surrounding style —
read the neighbours before you add a file.

## Tests

`pytest` from the repository root. Tests live beside the code they cover.
