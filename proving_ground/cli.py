"""Command line: run a series, re-score one, or scan a store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import PinnedConfig
from .epoch import run_series
from .leakage import scan
from .scoreboard import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proving-ground")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a series")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--epochs", type=int, default=4)
    run.add_argument("-k", "--trials", type=int, default=5)
    run.add_argument("--block-size", type=int, default=5)
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--model", default=PinnedConfig.model)
    run.add_argument("--arms", default="treatment,control,sham")
    run.add_argument("--budget", type=float, default=PinnedConfig.budget_usd)

    board = sub.add_parser("scoreboard", help="re-score a series from raw results")
    board.add_argument("--root", type=Path, required=True)
    board.add_argument("--out", type=Path)

    leak = sub.add_parser("scan", help="scan a store for evaluation leakage")
    leak.add_argument("store", type=Path)

    args = parser.parse_args(argv)

    if args.command == "run":
        config = PinnedConfig.resolve(model=args.model, budget_usd=args.budget)
        print(json.dumps(config.as_dict(), indent=2))
        run_series(
            root=args.root,
            epochs=args.epochs,
            k=args.trials,
            block_size=args.block_size,
            config=config,
            arms=[a for a in args.arms.split(",") if a],
            concurrency=args.concurrency,
        )
        page = render(args.root / "results.jsonl")
        (args.root / "SCOREBOARD.md").write_text(page)
        print(page)
        return 0

    if args.command == "scoreboard":
        page = render(args.root / "results.jsonl")
        if args.out:
            args.out.write_text(page)
        print(page)
        return 0

    report = scan(args.store)
    print(json.dumps(report.as_dict(), indent=2))
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
