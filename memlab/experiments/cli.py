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

from .. import providers
from . import analysis, compiler, runner, spec as spec_module
from .store import ResultStore


def _load(path: str) -> spec_module.Spec:
    return spec_module.load(path)


def _block(value) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        return {"model": value}
    return {}


def apply_model_args(spec: spec_module.Spec, args) -> None:
    """Apply CLI provider overrides to the spec environment (no key values)."""
    environment = spec.data.setdefault("environment", {})
    llm = _block(environment.get("llm"))
    for key, value in (("provider", getattr(args, "provider", None)),
                       ("model", getattr(args, "model", None)),
                       ("base_url", getattr(args, "base_url", None)),
                       ("api_key_env", getattr(args, "api_key_env", None))):
        if value:
            llm[key] = value
    environment["llm"] = llm
    embedding = _block(environment.get("embedding"))
    for key, value in (("provider", getattr(args, "embedding_provider", None)),
                       ("model", getattr(args, "embedding_model", None)),
                       ("base_url", getattr(args, "embedding_base_url", None)),
                       ("api_key_env", getattr(args, "embedding_api_key_env", None))):
        if value:
            embedding[key] = value
    if embedding:
        environment["embedding"] = embedding


def preflight(spec: spec_module.Spec) -> dict:
    environment = spec.data.get("environment") or {}
    llm = _block(environment.get("llm"))
    embedding = _block(environment.get("embedding"))
    return {"llm": providers.preflight(llm), "embedding": providers.preflight(embedding)}


def partition_plans(plans):
    """Split compiled plans into the formal matrix and the excluded reasons."""
    valid = [plan for plan in plans if plan.valid]
    unrunnable = [plan for plan in plans if not plan.runnable]
    no_op = [plan for plan in plans if plan.runnable and plan.no_op_factors]
    duplicates = sum(len(plan.aliases) for plan in plans)
    return valid, unrunnable, no_op, duplicates


def _summary(spec, plans, selected, *, out=None, dry_run=True) -> dict:
    valid, unrunnable, no_op, duplicates = partition_plans(plans)
    deferred = spec.deferred
    return {
        "spec": spec.id, "design": spec.design,
        "runs": len(plans), "valid_runs": len(valid), "selected_runs": len(selected),
        "excluded_unrunnable": len(unrunnable), "excluded_no_op": len(no_op),
        "duplicates": duplicates,
        # A removed level is never silent: sweep always reports what left the
        # matrix, why, and which blocked resource it waits on.
        "deferred_factors": len(deferred),
        "deferred": [
            {"id": item.get("id"), "levels": list(item.get("levels") or []),
             "status": item.get("status"), "reason": item.get("reason")}
            for item in deferred
        ],
        "out": out, "dry_run": bool(dry_run),
    }


def cmd_sweep(args) -> int:
    spec = _load(args.spec)
    apply_model_args(spec, args)
    plans = compiler.compile_spec(spec)
    selected = plans if args.include_invalid else [plan for plan in plans if plan.valid]
    if args.out:
        compiler.write_matrix(selected, args.out)
    print(json.dumps(_summary(spec, plans, selected, out=args.out, dry_run=args.dry_run),
                     ensure_ascii=False, indent=2))
    if args.verbose:
        for plan in plans[: args.show]:
            print(json.dumps({"run_id": plan.run_id, "factors": plan.factors,
                              "runnable": plan.runnable, "valid": plan.valid,
                              "runnable_reasons": list(plan.runnable_reasons),
                              "no_op_factors": list(plan.no_op_factors),
                              "warnings": list(plan.warnings),
                              "aliases": len(plan.aliases),
                              "notes": list(plan.notes)}, ensure_ascii=False))
    return 0


def cmd_run(args) -> int:
    spec = _load(args.spec)
    apply_model_args(spec, args)
    if getattr(args, "preflight", False) and args.executor == "e2e" and not args.offline:
        try:
            report = preflight(spec)
        except Exception as exc:
            print(json.dumps({"error": f"{type(exc).__name__}: {exc}", "ready": False},
                             ensure_ascii=False, indent=2))
            return 2
        print(json.dumps({"preflight": report}, ensure_ascii=False, indent=2))
    plans = compiler.compile_spec(spec)
    selected = plans if args.include_invalid else [plan for plan in plans if plan.valid]
    if not selected:
        raise ValueError("no valid plans to run; compile with --include-invalid to inspect them")
    if args.dry_run:
        print(json.dumps(_summary(spec, plans, selected, dry_run=True), ensure_ascii=False, indent=2))
        return 0
    # Only an explicit --samples overrides per-plan datasets; --limit still lets
    # each plan keep its own conversations while capping the question count.
    questions = runner.load_questions(spec, limit=args.limit, samples=args.samples) if args.samples is not None else None
    executor = runner.make_executor(getattr(args, "executor", "legacy"),
                                    offline=getattr(args, "offline", False))
    with ResultStore(args.db) as store:
        machine = runner.Runner(store, executor=executor, limit=args.limit, shard=args.shard,
                                shards=args.shards, resume=not args.no_resume,
                                retry_errors=args.retry_errors, log=print)
        results = machine.run(spec, selected, questions=questions)
    print(json.dumps({"spec": spec.id, "runs": len(selected), "results": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_analyze(args) -> int:
    with ResultStore(args.db) as store:
        rows = analysis.run_table(store, args.metric)
    print(json.dumps({"metric": args.metric, "rows": rows}, ensure_ascii=False, indent=2))
    return 0


def add_model_args(parser: argparse.ArgumentParser, *, with_preflight: bool = False) -> None:
    parser.add_argument("--provider", default=None,
                        choices=("ollama", "openai_compatible", "deepseek", "dashscope", "qwen", "openrouter"))
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--embedding-provider", default=None,
                        choices=("ollama", "openai_compatible", "deepseek", "dashscope", "qwen", "openrouter"))
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--embedding-base-url", default=None)
    parser.add_argument("--embedding-api-key-env", default=None)
    if with_preflight:
        parser.add_argument("--preflight", action="store_true",
                            help="check provider/key/model before running e2e")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MemLab experiment control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    sweep = sub.add_parser("sweep", help="compile a spec into a run matrix")
    sweep.add_argument("--spec", required=True)
    sweep.add_argument("--out", default=None, help="write matrix JSON here")
    sweep.add_argument("--dry-run", action="store_true")
    sweep.add_argument("--verbose", action="store_true")
    sweep.add_argument("--show", type=int, default=5)
    sweep.add_argument("--include-invalid", action="store_true",
                       help="write plans that are not runnable or vary a no-op axis")
    add_model_args(sweep)
    sweep.set_defaults(func=cmd_sweep)

    run = sub.add_parser("run", help="compile and execute a spec")
    run.add_argument("--spec", required=True)
    run.add_argument("--db", default="runs/s5.sqlite")
    run.add_argument("--limit", type=int, default=None,
                     help="questions per conversation; overrides the plan dataset count but keeps its samples")
    run.add_argument("--samples", nargs="+", default=None,
                     help="explicit conversations; overrides every plan's dataset")
    run.add_argument("--shard", type=int, default=0)
    run.add_argument("--shards", type=int, default=1)
    run.add_argument("--no-resume", action="store_true")
    run.add_argument("--retry-errors", action="store_true",
                     help="re-run questions whose previous result was an error")
    run.add_argument("--include-invalid", action="store_true",
                     help="also run plans that are not runnable or vary a no-op axis (debug only)")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--executor", choices=("legacy", "e2e"), default="legacy",
                     help="legacy = Runtime/legacy methods; e2e = S4 module pipeline")
    run.add_argument("--offline", action="store_true",
                     help="e2e only: deterministic offline clients when Ollama is unavailable")
    add_model_args(run, with_preflight=True)
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
