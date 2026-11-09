#!/usr/bin/env python3
"""Add B0 and R0 baseline runs to an E1.1 adoption result DB.

`single_factor_adoption` compiles only add/remove-one-component plans; it does
not include a standalone B0 or R0 plan.  The adoption deltas need those two
references, so this script runs them once on the same question set and writes
them into the same SQLite store as ordinary Runner runs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab.experiments import compiler, runner, spec as spec_module
from memlab.experiments.executor import make_e2e_executor
from memlab.experiments.store import ResultStore


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default="configs/experiments/e1-adoption.json")
    parser.add_argument("--db", default="runs/adoption/adoption.sqlite")
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args(argv)

    spec = spec_module.load(args.spec)
    machine = compiler.Compiler(spec)
    questions = runner.load_questions(spec, limit=args.limit)
    executor = make_e2e_executor(offline=True)
    with ResultStore(args.db) as store:
        for index, (key, label) in enumerate((("off", "B0"), ("on", "R0"))):
            plan = machine._plan(900 + index, machine._base(key),
                                 factors={"module": "__baseline__", "baseline": label})
            if store.get_run(plan.run_id) is not None:
                print(f"skip existing {plan.run_id}")
                continue
            result = runner.Runner(store, executor=executor, limit=args.limit, resume=False).run_plan(
                plan, questions)
            print(f"{key.upper()}: {plan.run_id} {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
