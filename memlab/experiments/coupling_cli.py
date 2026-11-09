"""CLI for E2 coupling analysis.

    python -m memlab.experiments.coupling_cli --db runs/e1.sqlite
    python -m memlab.experiments.coupling_cli --db ... --run <run_id> --gate evidence_recall
    python -m memlab.experiments.coupling_cli --db ... --system-run A --oracle-run B
"""
from __future__ import annotations

import argparse
import json
import sys

from . import coupling
from .store import ResultStore


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="E2 coupling analysis")
    p.add_argument("--db", required=True)
    p.add_argument("--run", default=None, help="one run: conversion + bottleneck")
    p.add_argument("--system-run", default=None)
    p.add_argument("--oracle-run", default=None)
    p.add_argument("--gate", default="evidence_recall")
    p.add_argument("--gate-min", type=float, default=1.0)
    p.add_argument("--outcome", default="answer_f1")
    p.add_argument("--metric", default="answer_f1")
    p.add_argument("--factor", default="module")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with ResultStore(args.db) as store:
            if args.system_run and args.oracle_run:
                payload = {"oracle_gap": coupling.oracle_gap(store, args.system_run, args.oracle_run, args.metric)}
            elif args.run:
                payload = {
                    "conversion": coupling.conversion(
                        store, args.run, gate=args.gate, gate_min=args.gate_min, outcome=args.outcome
                    ).to_dict(),
                    "bottleneck": coupling.bottleneck(
                        store, args.run, gate=args.gate, outcome=args.outcome
                    ),
                }
            else:
                payload = {
                    "conversion": coupling.conversion_table(
                        store, gate=args.gate, gate_min=args.gate_min, outcome=args.outcome
                    ),
                    "groups": coupling.group_metric(store, args.metric, factor=args.factor),
                    "llm": coupling.llm_attribution(store, args.metric),
                }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
