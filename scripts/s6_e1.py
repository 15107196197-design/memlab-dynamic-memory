#!/usr/bin/env python3
"""S6 E1 module screening.

Runs six module-internal candidate sets (W/S/R/M/U/K) through the S5 Runner with
the S4 E2E executor.  Offline mode is used when Ollama is unavailable; its answer
F1 is an extractive baseline and is labelled as such in the report.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import statistics
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab import cache as lab_cache
from memlab import config as lab_config
from memlab import legacy, manifest
from memlab.experiments import compiler, executor, runner, store as store_module
from memwb import dataset, evaluation

BASE_R0 = lab_config.RunConfig.load(ROOT / "configs" / "reference-r0.json").to_dict()
SAMPLE_ID = "conv-26"


def config_from(base: dict, overrides: dict) -> dict:
    config = copy.deepcopy(base)
    for path, value in overrides.items():
        compiler.set_path(config, path, value)
    return config


def candidate_config(overrides: dict) -> dict:
    return config_from(BASE_R0, overrides)


def _w_overrides(schema: str, resolver: str, auditor: str) -> dict:
    overrides = {
        "schema": {"impl": schema, "params": copy.deepcopy(BASE_R0["schema"]["params"])},
        "write.resolver": {"impl": resolver, "params": {}},
        "write.auditor": {"impl": auditor, "params": {}},
    }
    if schema == "legacy_flat":
        overrides["schema"]["params"] = {"extract_model": "qwen3.8:27b-q4_K_M"}
        overrides["temporal"] = {"model": "version_chain", "params": {"conflict_policy": "keep_both"}}
    return overrides


def state_rich_base() -> dict:
    """Fixed W for S/U/K: meta schema + append preserves historical versions."""
    return candidate_config(_w_overrides("meta_schema", "append", "none"))


def u_base() -> dict:
    """U needs a context that still contains historical versions (no stale filter)."""
    config = state_rich_base()
    for name in ("filter", "mmr", "decay", "compress"):
        compiler.set_path(config, f"post.{name}", {"impl": "none", "params": {}})
    return config


def _m_overrides(fusion: str, rerank: str, post: dict) -> dict:
    overrides = {
        "fusion": {"impl": fusion, "params": (
            {"rrf_k": 60} if fusion == "rrf" else
            {"rrf_k": 60, "weights": {"bm25": 1.0, "dense": 0.7, "temporal": 1.2, "graph_khop": 1.0}})},
        "rerank": {"impl": rerank, "params": (
            {} if rerank == "none" else {"model": "BAAI/bge-reranker-v2-m3", "top_n": 50})},
    }
    for name in ("mmr", "filter", "decay", "compress"):
        overrides[f"post.{name}"] = post.get(name, {"impl": "none", "params": {}})
    return overrides


CANDIDATES = {
    "W": [
        {"name": "W1-legacy-append", "role": "cost", "config": candidate_config(_w_overrides("legacy_flat", "append", "none"))},
        {"name": "W2-meta-append", "role": "balanced", "config": candidate_config(_w_overrides("meta_schema", "append", "none"))},
        {"name": "W3-meta-mem0", "role": "quality", "config": candidate_config(_w_overrides("meta_schema", "mem0_4action", "llm_audit"))},
    ],
    "S": [
        {"name": "S1-state-slot", "role": "cost", "config": config_from(state_rich_base(), {"graph.repr": {"impl": "state_slot", "params": {}}})},
        {"name": "S2-entity-triple", "role": "balanced", "config": config_from(state_rich_base(), {"graph.repr": {"impl": "entity_triple", "params": {"max_neighbors": 40, "incremental": True}}})},
        {"name": "S3-three-layer", "role": "quality", "config": config_from(state_rich_base(), {"graph.repr": {"impl": "three_layer", "params": {"layers": ["entity", "event", "topic"], "incremental": True}}})},
    ],
    "R": [
        {"name": "R1-planner-none", "role": "cost", "config": candidate_config({"planner": {"impl": "none", "params": {"k": 15}}})},
        {"name": "R2-rule-router", "role": "balanced", "config": candidate_config({})},
        {"name": "R3-dag", "role": "quality", "config": candidate_config({"planner": {"impl": "dag", "params": {"granularity": "medium", "parallelism": 1, "analyzer": "rule"}}})},
    ],
    "M": [
        {"name": "M1-rrf", "role": "cost", "config": candidate_config(_m_overrides("rrf", "none", {}))},
        {"name": "M2-weighted-compress", "role": "balanced", "config": candidate_config(_m_overrides(
            "weighted_rrf", "cross_encoder", {"compress": {"impl": "extractive", "params": {"budget_tokens": 1000}}}))},
        {"name": "M3-query-adaptive", "role": "quality", "config": candidate_config({})},
    ],
    "U": [
        {"name": "U1-none-direct", "role": "cost", "config": config_from(u_base(), {"logic.state_resolver": "none", "answer": {"impl": "direct", "params": {}}})},
        {"name": "U2-offline-valid", "role": "balanced", "config": config_from(u_base(), {"logic.state_resolver": "offline_slot", "answer": {"impl": "valid_history", "params": {}}})},
        {"name": "U3-offline-chain", "role": "quality", "config": config_from(u_base(), {"logic.state_resolver": "offline_slot", "answer": {"impl": "evidence_chain", "params": {}}})},
    ],
    "K": [
        {"name": "K1-none", "role": "baseline", "action": "none", "params": {}, "config": state_rich_base()},
        {"name": "K2-dedupe", "role": "balanced", "action": "consolidate", "params": {"threshold": 0.9}, "config": state_rich_base()},
        {"name": "K3-archive", "role": "quality", "action": "archive", "params": {"age_days": 90}, "config": state_rich_base()},
    ],
}


def select_questions(sample_id: str, limit: int, seed: int) -> list:
    sample = dataset.store().get(sample_id)
    eligible = evaluation.answerable(sample.get("qa", []))
    groups: dict[int, list] = defaultdict(list)
    for index, qa in eligible:
        groups[qa.get("category")].append((index, qa))
    rng = random.Random(seed)
    for values in groups.values():
        rng.shuffle(values)
    selected = []
    categories = sorted(groups)
    while len(selected) < min(limit, len(eligible)):
        progressed = False
        for category in categories:
            if groups[category] and len(selected) < limit:
                selected.append(groups[category].pop())
                progressed = True
        if not progressed:
            break
    return [runner.Question(sample_id, index, qa) for index, qa in selected]


def make_plan(module: str, candidate: dict, seed: int, question_limit: int):
    config = copy.deepcopy(candidate["config"])
    config.setdefault("environment", {})["seed"] = seed
    lab_config.RunConfig.from_dict(config)  # validate before the run starts
    digest = lab_config.digest(config)
    run_id = f"s6-{module}-{candidate['name']}-s{seed}-{digest.split(':')[-1][:8]}"
    return compiler.RunPlan(
        run_id=run_id, spec_id="S6-E1-MODULES", design="module_screening",
        config=config, requested_config=config, effective_config=config, config_hash=digest,
        environment=config.get("environment"), dataset={"samples": [SAMPLE_ID], "question_limit": question_limit},
        factors={"module": module, "candidate": candidate["name"], "seed": seed},
        notes=("offline_extractive",),
    )


def summarize(store: store_module.ResultStore, run_id: str, n: int) -> dict:
    grouped = defaultdict(list)
    for row in store.metrics(run_id=run_id):
        grouped[row["metric"]].append(row["value"])
    metrics = {name: round(statistics.mean(values), 4) for name, values in grouped.items()
               if name != "error" and values}
    if grouped.get("seconds"):
        ordered = sorted(grouped["seconds"])
        metrics["p95_seconds"] = round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 4)
    errors = len(grouped.get("error", []))
    return {"run_id": run_id, "n": n, "errors": errors,
            "error_rate": round(errors / n, 4) if n else None, "metrics": metrics}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run S6 module screening")
    parser.add_argument("--questions", type=int, default=60)
    parser.add_argument("--seeds", type=int, nargs="+", default=[13, 17])
    parser.add_argument("--db", default=str(ROOT / "runs" / "s6" / "e1.sqlite"))
    parser.add_argument("--out", default=str(ROOT / "eval" / "archive" / "s6-e1-screening.json"))
    parser.add_argument("--cache", default=str(ROOT / "runs" / "s6" / "cache"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--online", action="store_true",
                        help="use Ollama instead of offline clients (requires a running model server)")
    args = parser.parse_args(argv)

    db = Path(args.db)
    if not args.resume:
        for path in (db, db.with_name("e1.sqlite-wal"), db.with_name("e1.sqlite-shm")):
            path.unlink(missing_ok=True)
    db.parent.mkdir(parents=True, exist_ok=True)
    cache = lab_cache.ArtifactCache(Path(args.cache))
    offline = not args.online
    e2e = executor.make_e2e_executor(offline=offline, cache=cache)
    k_executors = {
        "none": executor.make_k_executor(policy="none", params={}, offline=offline, cache=cache),
        "consolidate": executor.make_k_executor(policy="consolidate", params={"threshold": 0.9},
                                                offline=offline, cache=cache),
        "archive": executor.make_k_executor(policy="archive", params={"age_days": 90},
                                            offline=offline, cache=cache),
    }
    questions = {seed: select_questions(SAMPLE_ID, args.questions, seed) for seed in args.seeds}
    results = []
    with store_module.ResultStore(db) as store:
        for module, candidates in CANDIDATES.items():
            for candidate in candidates:
                for seed in args.seeds:
                    plan = make_plan(module, candidate, seed, args.questions)
                    execute = k_executors[candidate["action"]] if module == "K" else e2e
                    machine = runner.Runner(store, executor=execute, resume=False)
                    outcome = machine.run_plan(plan, questions[seed])
                    summary = summarize(store, plan.run_id, len(questions[seed]))
                    try:
                        run_config = lab_config.RunConfig.from_dict(plan.effective_config)
                        manifest.build_manifest(
                            run_config, prompts=legacy.PROMPTS, run_id=plan.run_id,
                            status="completed",
                        ).write(ROOT / "runs" / "s6" / "manifests" / f"{plan.run_id}.json")
                    except Exception:
                        pass
                    summary.update({"module": module, "candidate": candidate["name"],
                                    "role": candidate["role"], "seed": seed, "outcome": outcome})
                    results.append(summary)
                    print(json.dumps({key: summary[key] for key in ("run_id", "candidate", "seed", "errors")},
                                     ensure_ascii=False))

    # reproducibility: same candidate/questions, two independent databases
    reference_plan = make_plan("R", CANDIDATES["R"][1], args.seeds[0], args.questions)
    subset = questions[args.seeds[0]][:10]
    repeats = []
    with tempfile.TemporaryDirectory() as directory:
        for name in ("a", "b"):
            with store_module.ResultStore(Path(directory) / f"{name}.sqlite") as store:
                machine = runner.Runner(store, executor=executor.make_e2e_executor(offline=offline, cache=cache),
                                        resume=False)
                machine.run_plan(reference_plan, subset)
                repeats.append(summarize(store, reference_plan.run_id, len(subset)))
    deltas = {name: round(abs(repeats[0]["metrics"].get(name, 0) - repeats[1]["metrics"].get(name, 0)), 4)
              for name in ("evidence_recall", "ndcg", "answer_f1", "tokens")}
    reproducibility = {"run_id": reference_plan.run_id, "questions": len(subset),
                       "max_absolute_delta": max(deltas.values()), "deltas": deltas,
                       "within_0_01": max(deltas.values()) <= 0.01}

    by_module = defaultdict(list)
    for item in results:
        by_module[item["module"]].append(item)
    report = {
        "schema": "memlab/s6-e1@1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": manifest.git_commit(),
        "offline": offline,
        "ollama": not offline,
        "answer_f1_kind": "offline_extractive (not an LLM answer)" if offline else "local_llm",
        "dataset": {"samples": [SAMPLE_ID], "questions_per_seed": args.questions, "seeds": args.seeds},
        "modules": {
            module: [
                {
                    "candidate": item["candidate"], "role": item["role"], "seed": item["seed"],
                    "run_id": item["run_id"], "errors": item["errors"], "error_rate": item["error_rate"],
                    "metrics": item["metrics"],
                }
                for item in items
            ]
            for module, items in by_module.items()
        },
        "reproducibility": reproducibility,
        "limits": [
            "Ollama unavailable: embedding is deterministic hashing, answer F1 is extractive baseline.",
            "B-level Judge/F1 and real P95 are blocked_on_ollama.",
            "R0 configs run through E2E executor; Runtime guard remains fail-closed.",
            "cross_encoder falls back because sentence-transformers is not installed.",
            "K metrics are store-level and repeated per question.",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"db": str(db), "out": str(out), "runs": len(results),
                      "reproducibility": reproducibility}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
