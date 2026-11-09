#!/usr/bin/env python3
"""Run U1/U2/U3 on the annotated state benchmark and write state_accuracy.

The module pipeline's StateView is per retrieved MemoryUnit.  The benchmark labels
turn IDs (D25:1).  For each labelled turn we map it to the fact/turn units that
carry that evidence, then predict ACTIVE if any such unit is in StateView.valid,
HISTORICAL if any is in StateView.superseded, otherwise MISSING.  A turn that is
not in the merged context is MISSING (and counts as wrong), matching the legacy
state benchmark rule.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import statistics
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab import cache as lab_cache
from memlab import config as lab_config
from memlab import model
from memlab.e2e import E2EPipeline
from memlab.experiments import compiler, executor, spec as spec_module
from memlab.experiments.executor import build_context
from memlab.experiments.store import ResultStore


def load_candidates():
    path = ROOT / "scripts" / "s6_e1.py"
    spec = importlib.util.spec_from_file_location("s6_e1_state", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CANDIDATES["U"], module.make_plan


def units_by_turn(store):
    mapping = {}
    for unit in store.units:
        for span in unit.evidence:
            mapping.setdefault(span.turn_id, []).append(unit.memory_id)
        if unit.kind == "turn" and unit.structured.get("turn"):
            mapping.setdefault(str(unit.structured["turn"]), []).append(unit.memory_id)
    return mapping


def evaluate_item(item, ctx, pipeline):
    configured_k = int(ctx.config.get("retrieval.k", 15) or 15)
    retrieval = pipeline.runner.run(item["question"], ctx, k=max(1, configured_k))
    if item.get("as_of"):
        frame = replace(retrieval.frame, as_of=model.parse_time(item["as_of"]))
        retrieval = replace(retrieval, frame=frame)
    merged = pipeline.merger.run(retrieval, ctx.store, ctx)
    answer = pipeline.user.run(item["question"], merged, retrieval.frame, ctx.store, ctx)
    state = answer.state

    valid = {unit.memory_id for unit in state.valid}
    superseded = {unit.memory_id for unit in state.superseded}
    merged_ids = {unit.memory_id for unit in merged.units}
    mapping = units_by_turn(ctx.store)

    rows = []
    for turn, gold in item["memories"].items():
        unit_ids = mapping.get(turn, [])
        states = []
        for unit_id in unit_ids:
            if unit_id in valid:
                states.append("ACTIVE")
            elif unit_id in superseded:
                states.append("HISTORICAL")
            elif unit_id in merged_ids:
                states.append("UNRESOLVED")
            else:
                states.append("MISSING")
        if "ACTIVE" in states:
            predicted = "ACTIVE"
        elif "HISTORICAL" in states:
            predicted = "HISTORICAL"
        elif "UNRESOLVED" in states:
            predicted = "UNRESOLVED"
        else:
            predicted = "MISSING"
        rows.append({
            "turn": turn,
            "gold": gold,
            "predicted": predicted,
            "unit_ids": unit_ids,
            "retrieved": any(unit_id in merged_ids for unit_id in unit_ids),
            "correct": predicted == gold,
        })
    active_gold = {row["turn"] for row in rows if row["gold"] == "ACTIVE"}
    active_pred = {row["turn"] for row in rows if row["predicted"] == "ACTIVE"}
    return {
        "item_id": item["id"],
        "sample": item["sample"],
        "question": item["question"],
        "as_of": item.get("as_of"),
        "state_accuracy": sum(row["correct"] for row in rows) / len(rows) if rows else None,
        "valid_set_exact": int(active_gold == active_pred),
        "evidence_recall": sum(row["retrieved"] for row in rows) / len(rows) if rows else None,
        "labelled_memories": len(rows),
        "active_labelled": len(active_gold),
        "historical_labelled": sum(1 for row in rows if row["gold"] == "HISTORICAL"),
        "memories": rows,
        "predicted_state_counts": {
            state_name: sum(1 for row in rows if row["predicted"] == state_name)
            for state_name in ("ACTIVE", "HISTORICAL", "UNRESOLVED", "MISSING")
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="eval/archive/state-accuracy.json")
    parser.add_argument("--db", default="runs/state/state.sqlite")
    parser.add_argument("--benchmark", default="eval/state_benchmark.json")
    args = parser.parse_args(argv)

    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    items = benchmark["items"]
    candidates, make_plan = load_candidates()
    cache = lab_cache.ArtifactCache()
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    results = []
    context_by_run_sample = {}

    with ResultStore(db) as store:
        for candidate in candidates:
            plan = make_plan("U", candidate, 13, len(items), samples=sorted({item["sample"] for item in items}))
            store.upsert_run(plan, status="running")
            rows = []
            errors = 0
            for item in items:
                sample = item["sample"]
                key = (plan.config_hash, sample)
                if key not in context_by_run_sample:
                    context = build_context(plan, sample, offline=True, cache=cache)
                    context_by_run_sample[key] = (context, E2EPipeline(context))
                context, pipeline = context_by_run_sample[key]
                try:
                    row = evaluate_item(item, context, pipeline)
                    qid = f"{sample}:{item['id']}"
                    store.add_metric(plan.run_id, qid, "state_accuracy", row["state_accuracy"],
                                     meta={"item_id": item["id"], "labelled_memories": row["labelled_memories"]})
                    store.add_metric(plan.run_id, qid, "valid_set_exact", float(row["valid_set_exact"]),
                                     meta={"item_id": item["id"]})
                    store.add_metric(plan.run_id, qid, "evidence_recall", row["evidence_recall"],
                                     meta={"item_id": item["id"]})
                    store.add_metric(plan.run_id, qid, "state_labelled", float(row["labelled_memories"]),
                                     meta={"item_id": item["id"]})
                    rows.append(row)
                except Exception as exc:  # failures are data
                    errors += 1
                    qid = f"{sample}:{item['id']}"
                    store.add_metric(plan.run_id, qid, "error", 1.0,
                                     meta={"type": type(exc).__name__, "message": str(exc)[:500]})
            store.set_status(plan.run_id, "complete_with_errors" if errors else "complete")
            results.append({"run_id": plan.run_id, "candidate": candidate["name"],
                            "config_hash": plan.config_hash, "errors": errors, "items": rows})

    summary = {}
    for result in results:
        rows = result["items"]
        memories = [memory for row in rows for memory in row["memories"]]
        active = [memory for memory in memories if memory["gold"] == "ACTIVE"]
        historical = [memory for memory in memories if memory["gold"] == "HISTORICAL"]
        summary[result["candidate"]] = {
            "run_id": result["run_id"],
            "items": len(rows),
            "errors": result["errors"],
            "state_accuracy_item_mean": round(statistics.fmean([row["state_accuracy"] for row in rows]), 6) if rows else None,
            "state_accuracy_memory_pooled": round(sum(m["correct"] for m in memories) / len(memories), 6) if memories else None,
            "valid_set_exact": round(statistics.fmean([row["valid_set_exact"] for row in rows]), 6) if rows else None,
            "evidence_recall": round(statistics.fmean([row["evidence_recall"] for row in rows]), 6) if rows else None,
            "active_state_accuracy": round(sum(m["correct"] for m in active) / len(active), 6) if active else None,
            "historical_state_accuracy": round(sum(m["correct"] for m in historical) / len(historical), 6) if historical else None,
            "labelled_memories": len(memories),
            "as_of_items": sum(1 for row in rows if row.get("as_of")),
        }

    payload = {
        "schema": "memlab/state-accuracy@1",
        "experiment_id": "E1-U-state-accuracy",
        "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "offline": True,
        "level": "A-interface",
        "answer_f1_policy": "not reported: offline extractive is not an LLM answer",
        "judge_policy": "not reported: no judge in offline A-level run",
        "benchmark": str(args.benchmark),
        "source_db": str(db),
        "benchmark_note": benchmark.get("annotation"),
        "dataset": {
            "items": len(items),
            "samples": sorted({item["sample"] for item in items}),
            "as_of_items": sum(1 for item in items if item.get("as_of")),
        },
        "method": {
            "state_accuracy": "fraction of labelled turns whose predicted state matches gold (per item mean and memory-pooled)",
            "valid_set_exact": "predicted ACTIVE labelled-turn set equals gold ACTIVE set",
            "evidence_recall": "fraction of labelled turns represented by any unit in the merged context",
            "missing_policy": "a labelled turn with no unit in the merged context is MISSING and counts as wrong",
        },
        "candidates": results,
        "summary": summary,
        "limitations": [
            "Offline hash embedding is not semantic; the extractive answer is not an LLM answer.",
            "The benchmark has 17 items from conv-41/conv-42 (test conversations), not the 4 development conversations used by E1.1.",
            "U1/U2/U3 use offline_slot/state resolvers; as_of items cannot be fully respected by offline_slot.",
            "State labels are turn-level; mapping to module fact units uses evidence spans, so a turn with no fact unit is MISSING.",
            "A-level interface metric only; no answer F1 and no Judge.",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for name, row in summary.items():
        print(name, row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
