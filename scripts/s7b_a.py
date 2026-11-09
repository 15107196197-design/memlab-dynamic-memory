#!/usr/bin/env python3
"""S7b-A: offline, read-only coupling screen over the S6 SQLite runs.

This is an **A-level** screen.  It reads per-question metrics that already exist
in ``runs/s6/e1.sqlite``; it does not run an E1 plan, call a model, build an
Oracle run or claim a causal module effect.  Use S7b-B once Ollama/API answer
metrics exist.

    python scripts/s7b_a.py --db runs/s6/e1.sqlite \
      --out eval/archive/s7b-a-offline.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab.experiments import coupling
from memlab.experiments.store import ResultStore


def _fmt(value: object) -> str:
    if value is None:
        return "  n/a"
    if isinstance(value, float):
        return f"{value:7.4f}"
    return str(value)


def _table(title: str, rows: list[dict], key: str) -> None:
    print(f"\n{title}")
    print(f"{key:<12} runs gated  P(A)  P(A|R)   lift")
    for row in rows:
        print(f"{str(row.get(key)):<12} {row['runs']:>4} {row['n_gated']:>5} "
              f"{_fmt(row['p_outcome'])} {_fmt(row['p_outcome_given_gate'])} "
              f"{_fmt(row['lift_mean'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S7b-A offline coupling screen")
    parser.add_argument("--db", default=str(ROOT / "runs" / "s6" / "e1.sqlite"))
    parser.add_argument("--out", default=str(ROOT / "eval" / "archive" / "s7b-a-offline.json"))
    parser.add_argument("--gate", default="evidence_recall")
    parser.add_argument("--gate-min", type=float, default=1.0)
    parser.add_argument("--outcome", default="answer_f1")
    parser.add_argument("--outcome-min", type=float, default=0.0)
    args = parser.parse_args(argv)

    with ResultStore(args.db) as store:
        payload = coupling.screen(store, gate=args.gate, gate_min=args.gate_min,
                                  outcome=args.outcome, outcome_min=args.outcome_min)
    payload["db"] = str(args.db)
    payload["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("S7b-A offline coupling screen (A level; answer_f1 is extractive, not LLM)")
    print(f"db={args.db}")
    print(f"gate={args.gate}>={args.gate_min}  outcome={args.outcome}>{args.outcome_min}")
    print(f"runs={len(payload['runs'])}  oracle_gap={payload['oracle_gap']['status']}  "
          f"llm_attribution={payload['llm_attribution']['status']}")
    _table("By module", payload["by_module"], "module")
    _table("By candidate", payload["by_candidate"], "candidate")
    _table("By seed", payload["by_seed"], "seed")
    print("\nGate availability:")
    for row in payload["gate_availability"]:
        print(f"  {row['metric']:<18} {row['status']:<8} rows={row['rows']:<6} runs={row['runs']}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
