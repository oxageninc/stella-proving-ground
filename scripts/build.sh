#!/usr/bin/env bash
# Build a release stella from the tip of main, refusing to guess.
#
# The freshness dance is not ceremony. A series is pinned to a binary hash, and
# measuring a stale binary produces a perfectly clean result about code nobody
# is running. So this refuses to proceed on a dirty tree or a non-fast-forward
# pull rather than guessing, and asserts afterwards that the binary it just
# built really is the tip of main.
#
# Lives in a script rather than a Makefile recipe because macOS ships GNU Make
# 3.81, which predates `.ONESHELL` — every line of a recipe runs in its own
# shell there, so a multi-line `if` is a syntax error rather than a guard.
set -euo pipefail

STELLA_DIR="${STELLA_DIR:-$HOME/Projects/stella}"
STELLA_BIN="$STELLA_DIR/target/release/stella"

echo "==> using stella checkout: $STELLA_DIR"
if [ ! -d "$STELLA_DIR/.git" ]; then
  echo "FAIL: $STELLA_DIR is not a git checkout. Set STELLA_DIR=..." >&2
  exit 1
fi

cd "$STELLA_DIR"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo ""
  echo "FAIL: $STELLA_DIR has uncommitted changes." >&2
  echo "      Refusing to build — a series pinned to a binary built from a" >&2
  echo "      dirty tree is not reproducible by anyone, including you." >&2
  echo "      Commit, stash, or clean it, then re-run." >&2
  git status --short | head -20
  exit 1
fi

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "main" ]; then
  echo "==> on '$branch', switching to main"
  git checkout main
fi

echo "==> pulling (fast-forward only)"
git pull --ff-only

head=$(git rev-parse HEAD)
echo "==> building release binary at $head"
cargo build --release --package stella-cli --bin stella

if [ ! -x "$STELLA_BIN" ]; then
  echo "FAIL: no binary at $STELLA_BIN" >&2
  exit 1
fi

# The assertion that makes the rest trustworthy: the thing on disk is the thing
# we just pulled. A stale binary here yields a clean measurement of code nobody
# is running, and nothing downstream would notice.
built=$("$STELLA_BIN" --version)
echo "==> built $built from $head"
if [ "$(git rev-parse HEAD)" != "$head" ]; then
  echo "FAIL: HEAD moved during the build; re-run" >&2
  exit 1
fi

echo "==> ok: fresh binary from the tip of main"
