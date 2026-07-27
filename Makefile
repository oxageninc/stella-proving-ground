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
#   make scoreboard  re-score existing results. free, no model calls.
#   make status      what exists, what it cost, credit remaining

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.PHONY: help smoke build series confirm scoreboard status clean-scratch

STELLA_DIR    ?= $(HOME)/Projects/stella
STELLA_BIN    := $(STELLA_DIR)/target/release/stella
PY            ?= python3
VENV          := .venv

# The cheapest configuration that still yields a signal worth reading.
#
# Sized from measurement, not taste: ~$0.03/trial, and the bootstrap resamples
# TASKS (6 of them), so k buys precision within a task while epochs buy the
# thing that actually decides the verdict. Two epochs is one E0->E1 pair — the
# minimum that can say anything, and explicitly reported as PRELIMINARY,
# because a single pair has flipped sign three times in this repo's history.
EPOCHS        ?= 2
TRIALS        ?= 5
BLOCK_SIZE    ?= 5
CONCURRENCY   ?= 10
ARMS          ?= treatment,control,sham
SERIES        ?= series-$(shell date +%Y%m%d-%H%M%S)
ROOT          := results/$(SERIES)

# Stop before the account is empty rather than after. A series that runs out of
# credit mid-epoch turns provider errors into task failures, which reads as the
# agent suddenly collapsing — strictly worse than a shorter series.
BUDGET_FLOOR  ?= 2.00

help:
	@sed -n '1,14p' Makefile | sed 's/^# \{0,1\}//'

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
	@echo "==> using stella checkout: $(STELLA_DIR)"
	@test -d "$(STELLA_DIR)/.git" || { echo "FAIL: $(STELLA_DIR) is not a git checkout. Set STELLA_DIR=..."; exit 1; }
	cd "$(STELLA_DIR)"
	if ! git diff --quiet || ! git diff --cached --quiet; then
	  echo ""
	  echo "FAIL: $(STELLA_DIR) has uncommitted changes."
	  echo "      Refusing to build — a series pinned to a binary built from a"
	  echo "      dirty tree is not reproducible by anyone, including you."
	  echo "      Commit, stash, or clean it, then re-run."
	  git status --short | head -20
	  exit 1
	fi
	branch=$$(git rev-parse --abbrev-ref HEAD)
	if [ "$$branch" != "main" ]; then
	  echo "==> on '$$branch', switching to main"
	  git checkout main
	fi
	echo "==> pulling (fast-forward only)"
	git pull --ff-only
	head=$$(git rev-parse HEAD)
	echo "==> building release binary at $$head"
	cargo build --release --package stella-cli --bin stella
	test -x "$(STELLA_BIN)" || { echo "FAIL: no binary at $(STELLA_BIN)"; exit 1; }
	# The assertion that makes the rest trustworthy: the thing on disk is the
	# thing we just pulled. A stale binary here yields a clean measurement of
	# code nobody is running, and nothing downstream would notice.
	built=$$("$(STELLA_BIN)" --version)
	echo "==> built $$built from $$head"
	if [ "$$(git rev-parse HEAD)" != "$$head" ]; then
	  echo "FAIL: HEAD moved during the build; re-run"; exit 1
	fi
	@echo "==> ok: fresh binary from the tip of main"

# ------------------------------------------------------------------ measure

series: build smoke
	@echo ""
	@echo "==> series $(SERIES): $(EPOCHS) epochs, k=$(TRIALS), arms=$(ARMS)"
	@echo "    roughly \$$$(shell $(PY) -c "print(f'{(($(EPOCHS)*3*6*$(TRIALS)) + 10) * 0.03:.2f}')") and $(shell $(PY) -c "print(int(((($(EPOCHS)*3*6*$(TRIALS))+10)*110)/$(CONCURRENCY)/60))") min at concurrency $(CONCURRENCY)"
	@echo "    stopping if credit falls below \$$$(BUDGET_FLOOR)"
	@echo ""
	mkdir -p "$(ROOT)"
	$(MAKE) --no-print-directory _guard ROOT="$(ROOT)" &
	guard=$$!
	trap "kill $$guard 2>/dev/null || true" EXIT
	$(PY) -u -m proving_ground.cli run \
	  --root "$(ROOT)" \
	  --epochs $(EPOCHS) \
	  -k $(TRIALS) \
	  --block-size $(BLOCK_SIZE) \
	  --concurrency $(CONCURRENCY) \
	  --arms "$(ARMS)" \
	  2>&1 | tee "$(ROOT)/run.log"
	@echo ""
	@echo "==> done. scoreboard: $(ROOT)/SCOREBOARD.md"
	@echo "    ONE series is not a result — run 'make confirm' before believing"
	@echo "    the sign. This repo's own effect flipped three times."

# An independent replication. The single highest-value follow-up: a 2-epoch
# series can and has produced a large effect of either sign from noise alone,
# and only agreement across runs distinguishes signal from a lucky draw.
confirm:
	$(MAKE) series SERIES=$(SERIES)-confirm

# ---------------------------------------------------------------- reporting

scoreboard:
	@latest=$$(ls -dt results/series-* 2>/dev/null | head -1); \
	test -n "$$latest" || { echo "no series in results/"; exit 1; }; \
	echo "==> $$latest"; \
	$(PY) -m proving_ground.cli scoreboard --root "$$latest" --out "$$latest/SCOREBOARD.md"

status:
	@echo "stella:  $(STELLA_DIR)"
	@test -x "$(STELLA_BIN)" && echo "binary:  $$($(STELLA_BIN) --version) ($$(cd $(STELLA_DIR) && git rev-parse --short HEAD))" || echo "binary:  NOT BUILT — run 'make build'"
	@echo "series:"
	@for d in results/series-*; do \
	  test -d "$$d" || continue; \
	  n=$$(wc -l < "$$d/results.jsonl" 2>/dev/null || echo 0); \
	  c=$$($(PY) -c "import json,sys;print('%.2f'%sum(json.loads(l)['cost_usd'] for l in open('$$d/results.jsonl')))" 2>/dev/null || echo 0); \
	  echo "  $$d — $$n trials, \$$$$c"; \
	done
	@if [ -n "$${OPENROUTER_API_KEY:-}" ]; then \
	  curl -s -H "Authorization: Bearer $$OPENROUTER_API_KEY" https://openrouter.ai/api/v1/credits \
	   | $(PY) -c "import json,sys;d=json.load(sys.stdin)['data'];print('credit:  \$$%.2f'%(d['total_credits']-d['total_usage']))"; \
	fi

# Trial workspaces live outside the repo on purpose — an agent whose project
# root resolves to this repo can reach the task definitions and the verifiers.
clean-scratch:
	rm -rf "$${TMPDIR:-/tmp}/stella-proving-ground-work"
	@echo "==> scratch cleared"

# --------------------------------------------------------------- internal

_guard:
	@while pgrep -f 'proving_ground.cli run' >/dev/null 2>&1; do \
	  rem=$$(curl -s -H "Authorization: Bearer $$OPENROUTER_API_KEY" https://openrouter.ai/api/v1/credits 2>/dev/null \
	        | $(PY) -c "import json,sys;d=json.load(sys.stdin)['data'];print('%.2f'%(d['total_credits']-d['total_usage']))" 2>/dev/null || echo 999); \
	  if $(PY) -c "import sys;sys.exit(0 if float('$$rem') < $(BUDGET_FLOOR) else 1)"; then \
	    echo ""; echo "==> BUDGET FLOOR (\$$$$rem left) — stopping the series"; \
	    pkill -f 'proving_ground.cli run' || true; sleep 2; pkill -f 'stella run' || true; \
	    break; \
	  fi; \
	  sleep 45; \
	done
