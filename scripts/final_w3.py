"""W3 final evaluation on the two held-out test conversations.

Frozen configs: reference-b0 vs reference-r0. No test-time tuning.
Offline clients (hashing embedding + extractive answer) unless --online is given.
Outputs a committed archive and the Web-visible report.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memlab import config as lab_config
from memlab import manifest as lab_manifest
from memlab import webapp
from memwb import config as legacy_config

ROOT = lab_config.ROOT
TEST_SAMPLES = list(legacy_config.SPLIT["test"])
CONFIGS = ("B0", "R0")


def p95(values):
    values = sorted(float(v) for v in values if v is not None)
    if not values:
        return None
    return round(values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))], 3)


def mean(values):
    values = [float(v) for v in values if v is not None]
    return round(statistics.mean(values), 4) if values else None


def bootstrap_ci(pairs, samples=1000, seed=2026):
    rng = random.Random(seed)
    n = len(pairs)
    if n < 2:
        return [None, None]
    deltas = []
    for _ in range(samples):
        values = [pairs[rng.randrange(n)][1] - pairs[rng.randrange(n)][0] for _ in range(n)]
        deltas.append(statistics.mean(values))
    deltas.sort()
    return [round(deltas[int(0.025 * samples)], 4), round(deltas[int(0.975 * samples) - 1], 4)]


def aggregate(rows):
    return {
        "questions": len(rows),
        "answer_f1": mean([r["answer_f1"] for r in rows]),
        "evidence_recall": mean([r["evidence_recall"] for r in rows]),
        "state_accuracy": None,
        "tokens": mean([r["tokens"] for r in rows]),
        "p95_latency_ms": p95([r["latency_ms"] for r in rows]),
        "error_rate": round(sum(1 for r in rows if not r.get("prediction")) / len(rows), 4) if rows else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=int, default=20, help="questions per test conversation per seed")
    parser.add_argument("--seeds", type=int, nargs="+", default=[13, 17])
    parser.add_argument("--offline", action="store_true", default=True)
    parser.add_argument("--online", action="store_true", help="use Ollama/API instead of offline clients")
    parser.add_argument("--context", type=int, default=None,
                        help="override LLM context (24GB GPUs should use 8192/16384)")
    args = parser.parse_args()
    offline = not args.online
    experiment_id = "final-w3-test-online" if not offline else "final-w3-test-offline"
    started = time.time()
    batches, rows_by_run = {}, {}
    for preset in CONFIGS:
        for sample_id in TEST_SAMPLES:
            for seed in args.seeds:
                body = {
                    "sample": sample_id, "preset": preset, "batch": True,
                    "questions": args.questions, "seed": seed, "offline": offline,
                }
                if args.context:
                    config_data = webapp._preset(preset).to_dict()
                    environment = config_data.setdefault("environment", {})
                    environment["context_budget"] = int(args.context)
                    environment.setdefault("llm", {})["context"] = int(args.context)
                    body["config"] = config_data
                    body.pop("preset", None)
                out = webapp.post("/api/v2/runs", body)
                key = (preset, sample_id, seed)
                batches[key] = out
                rows_by_run[key] = out["rows"]
                print(f"{preset} {sample_id} seed={seed}: "
                      f"F1={out['metrics']['answer_f1']} R={out['metrics']['evidence_recall']} "
                      f"tokens={out['metrics']['tokens']}", flush=True)

    def rows(preset):
        return [row for key, value in rows_by_run.items() if key[0] == preset for row in value]

    base_rows, cand_rows = rows("B0"), rows("R0")
    base_metrics, cand_metrics = aggregate(base_rows), aggregate(cand_rows)
    by_qid_base = {r["qid"]: r for r in base_rows}
    by_qid_cand = {r["qid"]: r for r in cand_rows}
    common = sorted(set(by_qid_base) & set(by_qid_cand))
    pairs = [(by_qid_base[q]["answer_f1"], by_qid_cand[q]["answer_f1"]) for q in common
             if by_qid_base[q]["answer_f1"] is not None and by_qid_cand[q]["answer_f1"] is not None]
    rpairs = [(by_qid_base[q]["evidence_recall"], by_qid_cand[q]["evidence_recall"]) for q in common
              if by_qid_base[q]["evidence_recall"] is not None and by_qid_cand[q]["evidence_recall"] is not None]
    f1_ci = bootstrap_ci(pairs)
    recall_ci = bootstrap_ci(rpairs)

    def by_category(preset_rows):
        groups = {}
        for row in preset_rows:
            groups.setdefault(str(row["category"]), []).append(row)
        return [{"category": k, "n": len(v), "answer_f1": mean([r["answer_f1"] for r in v]),
                 "evidence_recall": mean([r["evidence_recall"] for r in v])}
                for k, v in sorted(groups.items())]

    def by_seed(preset):
        values = []
        for seed in args.seeds:
            subset = [row for key, rs in rows_by_run.items() if key[0] == preset and key[2] == seed for row in rs]
            values.append({"seed": seed, **aggregate(subset)})
        return values

    stages = {}
    for key, out in batches.items():
        if key[0] != "R0":
            continue
        for step in out.get("stage_waterfall") or []:
            stages.setdefault(step["stage"], []).append(step["ms"])
    stage_waterfall = [{"stage": k, "ms": round(statistics.mean(v), 3)} for k, v in sorted(stages.items())]

    delta_f1 = round((cand_metrics["answer_f1"] or 0) - (base_metrics["answer_f1"] or 0), 4)
    if f1_ci[0] is not None and f1_ci[0] > 0:
        status = "supported"
        claim = f"R0 F1 +{delta_f1:.4f} over B0; 95% bootstrap CI {f1_ci} excludes 0."
    elif f1_ci[1] is not None and f1_ci[1] < 0:
        status = "not_supported"
        claim = f"R0 F1 {delta_f1:+.4f} vs B0; 95% bootstrap CI {f1_ci} excludes 0 in the negative direction."
    else:
        status = "inconclusive"
        claim = f"R0 F1 {delta_f1:+.4f} vs B0; 95% bootstrap CI {f1_ci} includes 0."
    model_label = legacy_config.answer_model() if not offline else "offline-extractive"
    embedding_label = legacy_config.embed_model() if not offline else "offline-hash"
    conclusion = {
        "status": status,
        "claims": [claim],
        "conditions": [
            "Frozen B0/R0 configs; no test-time tuning.",
            "Test split conv-41/conv-42; questions stratified by category.",
            ("Real model answer via the configured Ollama/API endpoint; this is a B-level LLM answer comparison."
             if not offline else
             "Offline extractive answer + hashing embedding; this is NOT an LLM-quality claim."),
        ],
        "limitations": [
            ("Local/remote model latency and API/network variance are part of P95; not a GPU-only latency claim."
             if not offline else "No real Ollama/API model: F1 is offline extractive, not B-level."),
            "state_accuracy is not recorded for the module pipeline; only F1/Recall are comparable.",
            "Two seeds and 20 questions/sample; bootstrap resamples questions, not conversations.",
            "No LLM-as-Judge in this comparison; F1 is the primary metric.",
        ],
        "next_actions": [
            ("If time allows, add a second judge or more candidates; do not tune on test."
             if not offline else "Re-run --online with the frozen configs when a model endpoint is available."),
            "Add state_accuracy from a frozen module-pipeline benchmark before reporting it.",
        ],
    }
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": experiment_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "manifest": {
            "git_commit": lab_manifest.git_commit(),
            "config_hashes": {preset: batches[(preset, TEST_SAMPLES[0], args.seeds[0])]["config_hash"] for preset in CONFIGS},
            "model": {"llm": model_label, "embedding": embedding_label},
            "offline": offline,
        },
        "dataset": {"split": "test", "samples": TEST_SAMPLES, "questions": len(base_rows),
                    "seeds": args.seeds, "test_only": True},
        "results": {
            "runs": [{"preset": preset, "sample": sample, "seed": seed,
                      "run_id": out["run_id"], "metrics": out["metrics"]}
                     for (preset, sample, seed), out in batches.items()],
            "metrics": cand_metrics,
            "baseline_metrics": base_metrics,
        },
        "comparisons": [
            {"baseline": "B0", "candidate": "R0", "metric": "answer_f1", "baseline_value": base_metrics["answer_f1"],
             "candidate_value": cand_metrics["answer_f1"], "delta": delta_f1, "ci95": f1_ci, "paired": True,
             "significant": f1_ci[0] is not None and (f1_ci[0] > 0 or f1_ci[1] < 0)},
            {"baseline": "B0", "candidate": "R0", "metric": "evidence_recall", "baseline_value": base_metrics["evidence_recall"],
             "candidate_value": cand_metrics["evidence_recall"],
             "delta": round((cand_metrics["evidence_recall"] or 0) - (base_metrics["evidence_recall"] or 0), 4),
             "ci95": recall_ci, "paired": True,
             "significant": recall_ci[0] is not None and (recall_ci[0] > 0 or recall_ci[1] < 0)},
        ],
        "analysis": {
            "main_effects": [{"factor": "config", "levels": ["B0", "R0"], "metrics": {"B0": base_metrics, "R0": cand_metrics}}],
            "interactions": [],
            "pareto": [],
            "by_category": {"B0": by_category(base_rows), "R0": by_category(cand_rows)},
            "by_seed": {"B0": by_seed("B0"), "R0": by_seed("R0")},
            "stage_waterfall": stage_waterfall,
            "failure_breakdown": [],
            "bootstrap": {"samples": 1000, "seed": 2026, "pairs_f1": len(pairs), "pairs_recall": len(rpairs)},
        },
        "conclusion": conclusion,
        "web": {"route": f"#/experiments/{experiment_id}", "published": True},
        "elapsed_seconds": round(time.time() - started, 1),
    }
    for path in (ROOT / "eval" / "archive" / f"{experiment_id}.json",
                 ROOT / "eval" / "archive" / "experiments" / f"{experiment_id}.json",
                 ROOT / "reports" / "experiments" / f"{experiment_id}.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", path)
    print(json.dumps({"experiment_id": experiment_id, "model": model_label,
                      "B0": base_metrics, "R0": cand_metrics, "delta_f1": delta_f1,
                      "f1_ci": f1_ci, "recall_ci": recall_ci, "conclusion": status},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
