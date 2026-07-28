# Contributing to textkit

House rules, deliberately different from any other project you may have seen.

## Adding a filter

1. Create `textkit/filters/<name>.py` exposing `apply(text: str, opts: dict) -> str`.
2. Add it to `PIPELINE` in `textkit/pipeline.py` as a `(name, module, order)`
   triple. Order decides where the filter runs; ties are a configuration error.

## Text

All text is handled as `str` and normalised to NFC on entry via
`normalize.nfc()`. Byte handling is confined to `io_layer.py`; a filter that
touches `bytes` is a bug.

## Errors

Raise `TextkitWarning` for recoverable issues — the driver collects warnings
and continues. Only `TextkitFatal` aborts the pipeline. Never raise builtins.

## Options

Filters read options through `opts.get(...)` with an explicit default. A
missing option is never an error; the default is the contract.
