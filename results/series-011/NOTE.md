# series-011 — two clean epochs, then a provider outage

**This is a 2-epoch series, not the 5 it was launched as.** The provider
died during E2 and the guard stopped the run. Read it as preliminary.

- **E0 and E1 are clean**: zero transport errors across all six arm-cells.
- **E2 is contaminated and excluded**: the only E2 rows in `results.jsonl`
  are 20 treatment trials that aborted with a transport error and zero
  model calls. No `epochs.jsonl` row was ever written for E2, so the
  scoreboard's "final epoch" is E1 and these rows score nothing. They are
  kept rather than deleted because raw results are published intact — but
  anything re-scoring this directory must keep excluding them.

Pinned to stella 0.5.73 (`7a1753754697`), a different binary from
series-009 (0.5.68) and failed-010 (0.5.71), because `make series`
rebuilds from the tip of main on every launch. This series is therefore
not a replication of either and stands alone.

`k=3`, not the pre-registered `k=5`, to fit a hard credit ceiling.
