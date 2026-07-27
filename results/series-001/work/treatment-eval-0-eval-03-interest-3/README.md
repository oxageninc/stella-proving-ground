# ledgerctl

A small double-entry ledger CLI. Commands are dispatched from a registry;
each command is a handler module under `ledgerctl/commands/`.

```
ledgerctl balance --account alice
ledgerctl transfer --from alice --to bob --amount 12.50
```

See `CONTRIBUTING.md` before adding a command.
