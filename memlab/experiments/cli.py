"""CLI for the experiment control plane.

    python -m memlab.experiments.cli sweep --spec configs/experiments/e1-adoption.json --dry-run
    python -m memlab.experiments.cli run --spec ... --db runs/s5.sqlite --limit 10
    python -m memlab.experiments.cli analyze --db runs/s5.sqlite --metric answer_f1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analysis, compiler, runner, spec as spec_module
from .store import ResultStore


def _load(path: str) -> spec_module.Spec:
    return spec_module.load(path)


def cmd_sweep(args) -> int:
    spec = _load(args.spec)
    plans = compiler.compile_spec(spec)
    if args.out:
        compiler.write_matrix(plans, args.out)
    print(json.dumps({
        "spec": spec.id, "design": spec.design, "runs": len(plans),
        "out": args.out, "dry_run": bool(args.dry_run),
    }, ensure_ascii=False, indent=2))
    if args.verbose:
        for plan in plans[: args.show]:
            print(json.dumps({"run_id": plan.run_id, "factors": plan.factors,
                              "notes": list(plan.notes)}, ensure_ascii=False))
    return 0


def cmd_run(args) -> int:
    spec = _load(args.spec)
    plans = compiler.compile_spec(spec)
    if args.dry_run:
        print(json.dumps({"spec": spec.id, "runs": len(plans), "dry_run": True}, ensure_ascii=False, indent=2))
        return 0
    questions = runner.load_questions(spec, limit=args.limit, samples=args.samples)
    with ResultStore(args.db) as store:
        machine = runner.Runner(store, limit=args.limit, shard=args.shard, shards=args.shards,
                                resume=not args.no_resume, log=print)
        results = machine.run(spec, plans, questions=questions)
    print(json.dumps({"spec": spec.id, "runs": len(plans), "results": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_analyze(args) -> int:
    with ResultStore(args.db) as store:
        rows = analysis.run_table(store, args.metric)
    print(json.dumps({"metric": args.metric, "rows": rows}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MemLab experiment control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    sweep = sub.add_parser("sweep", help="compile a spec into a run matrix")
    sweep.add_argument("--spec", required=True)
    sweep.add_argument("--out", default=None, help="write matrix JSON here")
    sweep.add_argument("--dry-run", action="store_true")
    sweep.add_argument("--verbose", action="store_true")
    sweep.add_argument("--show", type=int, default=5)
    sweep.set_defaults(func=cmd_sweep)

    run = sub.add_parser("run", help="compile and execute a spec")
    run.add_argument("--spec", required=True)
    run.add_argument("--db", default="runs/s5.sqlite")
    run.add_argument("--limit", type=int, default=None, help="questions per conversation")
    run.add_argument("--samples", nargs="+", default=None)
    run.add_argument("--shard", type=int, default=0)
    run.add_argument("--shards", type=int, default=1)
    run.add_argument("--no-resume", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)

    analyze = sub.add_parser("analyze", help="summarize a result database")
    analyze.add_argument("--db", default="runs/s5.sqlite")
    analyze.add_argument("--metric", default="answer_f1")
    analyze.set_defaults(func=cmd_analyze)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (spec_module.SpecError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
