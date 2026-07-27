# Proving ground — build a fresh Stella from main, then measure it.
#
# The freshness dance is not ceremony. A series is pinned to a binary hash, and
# measuring a stale binary produces a perfectly clean result about code nobody
# is running. So `build` refuses to proceed on a dirty tree or a non-fast-
# forward pull rather than guessing, and asserts afterwards that the binary it
# just built really is the tip of main.
#
#   make smoke       free. instrument check. run this before spending anything.
#   make build       fresh main -> release binary (fails loudly if it cannot)
#   make series      build + measure. THIS SPENDS MONEY.
#   make confirm     an independent replication, which is what makes it real
#   make probe       3-arm ceiling probe: does recall precision matter? SPENDS.
#   make scoreboard  re-score existing results. free, no model calls.
#   make status      what exists, what it cost, credit remaining
#
# Every recipe below is a single command. That is a constraint, not a style:
# macOS ships GNU Make 3.81, which predates `.ONESHELL`, so each line of a
# recipe runs in its own shell and a multi-line `if` is a syntax error rather
# than a guard. Multi-step logic lives in scripts/ where it is also readable
# and directly runnable.

SHELL         := /bin/bash
.PHONY: help smoke build series confirm probe scoreboard status clean-scratch

STELLA_DIR    ?= $(HOME)/Projects/stella
STELLA_BIN    := $(STELLA_DIR)/target/release/stella
PY            ?= python3
VENV          := .venv

# The cheapest configuration that still yields a signal worth reading.
#
# Sized from measurement, not taste: ~$0.026/trial. The bootstrap resamples
# TASKS, so the pool size decides the width of the interval while k buys
# precision within a task. Two epochs is one E0->E1 pair — the minimum that can
# say anything, and explicitly reported as PRELIMINARY, because a single pair
# has flipped sign three times in this repo's history.
EPOCHS        ?= 2
TRIALS        ?= 5
BLOCK_SIZE    ?= 5
CONCURRENCY   ?= 10
ARMS          ?= treatment,control,sham
SERIES        ?= series-$(shell date +%Y%m%d-%H%M%S)
ROOT          := results/$(SERIES)

# Probe sizing is separate: it has no epochs, and its three arms differ only in
# the context block appended to the prompt.
PROBE_TRIALS  ?= 4

# Stop before the account is empty rather than after. A series that runs out of
# credit mid-epoch turns provider errors into task failures, which reads as the
# agent suddenly collapsing — strictly worse than a shorter series.
BUDGET_FLOOR  ?= 2.00

export STELLA_DIR PY EPOCHS TRIALS BLOCK_SIZE CONCURRENCY ARMS BUDGET_FLOOR

help:
	@sed -n '1,16p' Makefile | sed 's/^# \{0,1\}//'

# ---------------------------------------------------------------- instrument

smoke: $(VENV)
	@echo "==> instrument check (free, no model calls)"
	$(VENV)/bin/python -m pytest tests/ -q
	@echo "==> ok: verifiers fail on an untouched corpus and pass on a reference"
	@echo "    solution, the leak gate fires and stays quiet correctly, and the"
	@echo "    corpus is pristine. Numbers from this harness mean something."

$(VENV):
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install -q pytest

# -------------------------------------------------------------------- build

build:
	@bash scripts/build.sh

# ------------------------------------------------------------------ measure

series: build smoke
	@ROOT="$(ROOT)" bash scripts/series.sh

# An independent replication. The single highest-value follow-up: a 2-epoch
# series can and has produced a large effect of either sign from noise alone,
# and only agreement across runs distinguishes signal from a lucky draw.
confirm:
	@$(MAKE) series SERIES=$(SERIES)-confirm

# The ceiling probe. Bypasses the lifecycle entirely — no store, no recall — and
# hand-delivers context in the prompt, to separate "the facts do not help" from
# "the facts never arrive". See experiments/precision_probe.py.
probe: smoke
	@$(VENV)/bin/python experiments/precision_probe.py $(PROBE_TRIALS)

# ---------------------------------------------------------------- reporting

scoreboard:
	@latest=$$(ls -dt results/series-* 2>/dev/null | head -1); test -n "$$latest" || { echo "no series in results/"; exit 1; }; echo "==> $$latest"; $(PY) -m proving_ground.cli scoreboard --root "$$latest" --out "$$latest/SCOREBOARD.md"

status:
	@echo "stella:  $(STELLA_DIR)"
	@test -x "$(STELLA_BIN)" && echo "binary:  $$($(STELLA_BIN) --version) ($$(cd $(STELLA_DIR) && git rev-parse --short HEAD))" || echo "binary:  NOT BUILT — run 'make build'"
	@echo "pool:    $$($(PY) -c "import sys;sys.path.insert(0,'.');from proving_ground.config import pool_digest;from proving_ground.tasks import load_pool;print('%s (%d eval, %d exp)'%(pool_digest(),len(load_pool('evaluation')),len(load_pool('experience'))))")"
	@echo "results:"
	@for d in results/*/; do test -f "$$d/results.jsonl" || continue; n=$$(wc -l < "$$d/results.jsonl"); c=$$($(PY) -c "import json;print('%.2f'%sum(json.loads(l)['cost_usd'] for l in open('$$d/results.jsonl') if l.strip()))" 2>/dev/null || echo 0); echo "  $$d — $$n trials, \$$$$c"; done
	@test -n "$${OPENROUTER_API_KEY:-}" && curl -s -H "Authorization: Bearer $$OPENROUTER_API_KEY" https://openrouter.ai/api/v1/credits | $(PY) -c "import json,sys;d=json.load(sys.stdin)['data'];print('credit:  \$$%.2f'%(d['total_credits']-d['total_usage']))" || true

# Trial workspaces live outside the repo on purpose — an agent whose project
# root resolves to this repo can reach the task definitions and the verifiers.
clean-scratch:
	rm -rf "$${TMPDIR:-/tmp}/stella-proving-ground-work"
	@echo "==> scratch cleared"
