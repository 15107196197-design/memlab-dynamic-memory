#!/usr/bin/env python3
"""Compare E1.2 parameter curves between seed 13 and seed 17.

The offline e2e path has deterministic hashing embeddings and an extractive
answer client; the seed primarily changes the effective config digest.  This
script measures whether that changes any A-level metric and flags levels whose
absolute delta exceeds 0.01 for the limitations section.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab.experiments import compiler, spec as spec_module

METRICS = ["evidence_recall", "ndcg", "tokens", "redundancy", "context_precision"]
SLUGS = {
    "schema.params.fields": "schema-fields",
    "schema.params.evidence": "schema-evidence",
    "graph.retrieval.params.k_hop": "graph-k-hop",
    "graph.retrieval.params.max_neighbors": "graph-max-neighbors",
    "retrieval.k": "planner-k",
    "post.mmr.params.lambda": "mmr-lambda",
    "post.decay.params.lambda": "decay-lambda",
    "post.compress.params.budget_tokens": "compress-budget",
    "rerank.params.top_n": "rerank-top-n",
}


def read_metrics(db: Path):
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    runs = {row["run_id"]: {"hash": row["config_hash"], "status": row["status"]}
            for row in connection.execute("SELECT run_id, config_hash, status FROM runs")}
    values = {}
    for row in connection.execute(
        "SELECT run_id, qid, metric, value FROM metrics WHERE metric IN (%s)"
        % ",".join("?" for _ in METRICS), METRICS
    ):
        values.setdefault(row["run_id"], {}).setdefault(row["metric"], {})[row["qid"]] = row["value"]
    errors = {row["run_id"]: row["n"] for row in connection.execute(
        "SELECT run_id, COUNT(*) AS n FROM metrics WHERE metric='error' GROUP BY run_id")}
    connection.close()
    return runs, values, errors


def plan_map(spec_path: Path):
    spec = spec_module.load(spec_path)
    machine = compiler.Compiler(spec)
    all_plans = machine._single_factor()
    kept = compiler.compile_spec(spec)
    by_factor = {}
    for plan in all_plans:
        factor_id = next(iter(plan.factors))
        by_factor[(factor_id, plan.factors[factor_id])] = plan.config_hash
    keep_hashes = {plan.config_hash for plan in kept}
    return spec, by_factor, keep_hashes


def mean(values):
    return statistics.fmean(values) if values else None


def pct(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-a", default="runs/params/p1.sqlite")
    parser.add_argument("--db-b", default="runs/params/p1-s17.sqlite")
    parser.add_argument("--spec-a", default="configs/experiments/e1-params.json")
    parser.add_argument("--spec-b", default="configs/experiments/e1-params-s17.json")
    parser.add_argument("--out", default="eval/archive/params-s17.json")
    args = parser.parse_args(argv)

    spec_a, map_a, _ = plan_map(Path(args.spec_a))
    spec_b, map_b, _ = plan_map(Path(args.spec_b))
    runs_a, values_a, errors_a = read_metrics(Path(args.db_a))
    runs_b, values_b, errors_b = read_metrics(Path(args.db_b))

    by_hash_a = {info["hash"]: run_id for run_id, info in runs_a.items()}
    by_hash_b = {info["hash"]: run_id for run_id, info in runs_b.items()}
    rows = []
    for factor in spec_a.factors:
        factor_id = str(factor["id"])
        for level in factor.get("levels") or []:
            hash_a = map_a[(factor_id, level)]
            hash_b = map_b[(factor_id, level)]
            run_a = by_hash_a.get(hash_a)
            run_b = by_hash_b.get(hash_b)
            if run_a is None or run_b is None:
                raise SystemExit(f"missing run for {factor_id}={level!r}: {run_a!r}, {run_b!r}")
            metrics = {}
            for metric in METRICS:
                a_values = values_a.get(run_a, {}).get(metric, {})
                b_values = values_b.get(run_b, {}).get(metric, {})
                common = sorted(set(a_values) & set(b_values))
                mean_a = mean([a_values[q] for q in common]) if common else None
                mean_b = mean([b_values[q] for q in common]) if common else None
                delta = (mean_b - mean_a) if mean_a is not None and mean_b is not None else None
                diffs = [b_values[q] - a_values[q] for q in common if a_values[q] != b_values[q]]
                metrics[metric] = {
                    "seed13": round(mean_a, 6) if mean_a is not None else None,
                    "seed17": round(mean_b, 6) if mean_b is not None else None,
                    "delta": round(delta, 6) if delta is not None else None,
                    "abs_delta": round(abs(delta), 6) if delta is not None else None,
                    "n_paired_questions": len(common),
                    "n_changed_questions": len(diffs),
                    "max_abs_question_delta": round(max((abs(d) for d in diffs), default=0.0), 6),
                    "exceeds_0.01": bool(delta is not None and abs(delta) > 0.01),
                }
            rows.append({
                "factor": factor_id,
                "level": level,
                "run_id_seed13": run_a,
                "run_id_seed17": run_b,
                "metrics": metrics,
                "errors": {"seed13": errors_a.get(run_a, 0), "seed17": errors_b.get(run_b, 0)},
            })

    summary = {}
    for metric in METRICS:
        deltas = [row["metrics"][metric]["abs_delta"] for row in rows
                  if row["metrics"][metric]["abs_delta"] is not None]
        summary[metric] = {
            "max_abs_delta": round(max(deltas), 6) if deltas else None,
            "n_levels_exceeding_0.01": sum(1 for row in rows if row["metrics"][metric]["exceeds_0.01"]),
        }

    payload = {
        "schema": "memlab/params-seed-compare@1",
        "experiment_id": spec_a.id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "offline": True,
        "level": "A-interface",
        "seed_a": 13,
        "seed_b": 17,
        "spec_a": str(args.spec_a),
        "spec_b": str(args.spec_b),
        "db_a": str(args.db_a),
        "db_b": str(args.db_b),
        "dataset": {
            "samples": list(spec_a.dataset.get("samples") or []),
            "question_limit": spec_a.dataset.get("question_limit"),
            "questions_per_level": rows[0]["metrics"]["tokens"]["n_paired_questions"] if rows else 0,
        },
        "summary": summary,
        "seed_effect_detected": any(item["n_levels_exceeding_0.01"] for item in summary.values()),
        "rows": rows,
        "limitations": [
            "Offline hash embedding is deterministic and the answer client is extractive; a zero seed delta is expected and does not mean the real LLM is seed-invariant.",
            "A-level interface metrics only; no answer F1, no Judge.",
            "Only 4 development conversations, 60 questions per conversation.",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print("max |seed17 - seed13|:", {key: value["max_abs_delta"] for key, value in summary.items()})
    print("levels >0.01:", {key: value["n_levels_exceeding_0.01"] for key, value in summary.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
