# textkit

A small text-processing CLI. Filters are dispatched from a pipeline table;
each filter is a module under `textkit/filters/`.

    textkit wrap --width 72 < input.txt
