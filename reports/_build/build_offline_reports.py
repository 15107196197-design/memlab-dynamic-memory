"""Build offline experiment reports from S6/S7b-A/W3 artifacts.

Read-only over runs/ and eval/; writes reports/experiments/*.json.
No LLM calls, no new experiment runs.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import compute_offline as C  # noqa: E402

NOW = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
REPORT_DIR = ROOT / "reports" / "experiments"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
HEAD = "2c1e22a11a204bc8f6648f0e3a565ac3f2ae03df"
DATA_COMMIT = C.archive.get("git_commit", "b4cf2f0")
ONLINE_PENDING = {
    "status": "pending",
    "expected_at": "2026-11-09T19:30:00+08:00",
    "reason": "Online/B-level run is executing in a separate session; this report uses offline data only.",
    "source": None,
    "results": None,
}


def online_pointer(report_id, *, seeds=(13,), questions=40, source="eval/archive/s6-e1-online-40.json"):
    return {
        "status": "complete",
        "report": f"{report_id}-online.json",
        "source": source,
        "model": "qwen3.8:27b-q4_K_M",
        "embedding": "bge-m3",
        "judge": "not_run",
        "seeds": list(seeds),
        "questions": questions,
        "note": "Online numbers are kept in the separate -online report; this report stays offline-only.",
    }


def online_not_run(reason):
    return {"status": "not_run", "report": None, "source": None, "reason": reason}

MODULE_META = OrderedDict([
    ("W", {
        "report_id": "E1-W1",
        "stage": "E1.1",
        "title": "W 写入实现选型（W1/W2/W3 候选）",
        "question": "schema / resolver / auditor 哪个组合能保住可追溯性与冲突？",
        "quality": "evidence_recall",
        "quality_label": "Recall",
        "metrics": ["evidence_recall", "ndcg", "field_completeness", "answer_f1", "tokens", "p95_latency_ms"],
        "baseline": "W1-legacy-append",
        "covers": ["E1-W1", "E1-W2", "E1-W3"],
        "report_commit": HEAD,
    }),
    ("S", {
        "report_id": "E1-S2",
        "stage": "E1.1",
        "title": "S 图表示插拔（state_slot / entity_triple / three_layer）",
        "question": "图表示更细是否提高检索召回与多跳覆盖，还是只增加构建/延迟成本？",
        "quality": "evidence_recall",
        "quality_label": "Recall",
        "metrics": ["evidence_recall", "ndcg", "graph_nodes", "graph_edges", "tokens", "p95_latency_ms"],
        "baseline": "S1-state-slot",
        "covers": ["E1-S2"],
        "report_commit": HEAD,
    }),
    ("R", {
        "report_id": "E1-R1",
        "stage": "E1.1",
        "title": "R 规划器插拔（none / rule_router / DAG）",
        "question": "规则/REAPER/DAG 哪个规划器提高计划质量与多跳召回？",
        "quality": "evidence_recall",
        "quality_label": "Recall",
        "metrics": ["evidence_recall", "ndcg", "plan_nodes", "tokens", "p95_latency_ms"],
        "baseline": "R1-planner-none",
        "covers": ["E1-R1"],
        "report_commit": HEAD,
    }),
    ("M", {
        "report_id": "E1-M1",
        "stage": "E1.1",
        "title": "M 融合/重排/后处理组合筛选（M1/M2/M3 候选）",
        "question": "RRF / weighted / adaptive，cross-encoder / filter / MMR / decay / compress 哪些有用？",
        "quality": "evidence_recall",
        "quality_label": "Recall",
        "metrics": ["evidence_recall", "ndcg", "redundancy", "tokens", "p95_latency_ms"],
        "baseline": "M1-rrf",
        "covers": ["E1-M1", "E1-M2", "E1-M3", "E1-M4", "E1-M5"],
        "report_commit": HEAD,
    }),
    ("U", {
        "report_id": "E1-U1",
        "stage": "E1.1",
        "title": "U 状态解析/上下文/回答器组合（U1/U2/U3 候选）",
        "question": "query_llm / offline_slot / bitemporal；direct / valid_history / evidence_chain 怎么选？",
        "quality": "evidence_recall",
        "quality_label": "Recall",
        "metrics": ["evidence_recall", "ndcg", "state_accuracy", "citations", "refused", "tokens", "p95_latency_ms"],
        "baseline": "U1-none-direct",
        "covers": ["E1-U1", "E1-U2", "E1-U4"],
        "report_commit": HEAD,
    }),
    ("K", {
        "report_id": "E1-K1",
        "stage": "E1.1",
        "title": "K 维护动作选型（none / dedupe / archive）",
        "question": "none / dedupe / archive 如何影响 staleness、contradiction、update correctness？",
        "quality": "update_correctness",
        "quality_label": "update_correctness",
        "metrics": ["staleness", "contradiction_rate", "update_correctness", "removed", "units"],
        "baseline": "K1-none",
        "covers": ["E1-K1", "E1-K2"],
        "report_commit": HEAD,
    }),
])

MODULE_CLAIMS = {
    "W": [
        "Offline A-level: W2 (meta_schema+append) Recall 0.5053 vs W1 0.4753 (+0.0300); nDCG 0.3553 vs 0.3644 (-0.0091); quality=Recall 0.5053, Tokens 306.9, P95 57.0 ms.",
        "W1 (legacy_flat+append) is cheaper/faster: Recall 0.4753, Tokens 311.5, P95 11.0 ms; W3 (meta+mem0+llm_audit) is dominated offline: Recall 0.4452, Tokens 350.8, P95 167.5 ms.",
        "Offline extractive F1 (W2 0.0289) is not an LLM F1; B-level W1/Judge/P95 remain blocked_on_ollama.",
    ],
    "S": [
        "Offline A-level: S1/S2/S3 all Recall 0.5053; nDCG 0.3563/0.3553/0.3553; graph representation adds no measurable offline recall/nDCG gain; quality=Recall 0.5053, Tokens 306.9, P95 9.0-92.5 ms.",
        "S3 three_layer has 1974 edges vs S1 752, but the larger graph did not raise recall; S3 P95 9.0 ms vs S1 92.5 ms, so no quality-cost trade-off was observed offline.",
        "R3 graph dispatch (13 configs x 61 multi-hop q): graph-novel candidates 34-91, but 0 survive fusion; final Recall 0.2372 across all impl/repr. This is a fusion/budget bottleneck.",
        "Real embedding and semantic graph retrieval are B-level; this report cannot claim graph value beyond the offline hash-embedding setup.",
    ],
    "R": [
        "Offline A-level: R3 DAG Recall 0.4704 = R1 none; nDCG 0.3696 vs 0.3711; quality=Recall 0.4704, Tokens 331.8, P95 19.5 ms (R3) vs 75.0 ms (R1).",
        "R2 rule_router is dominated offline: Recall 0.4452 (-0.0252), nDCG 0.3036, Tokens 350.8, P95 13.0 ms.",
        "Planner gain is not established: the analyzer is rule-based and embedding is offline hash; B-level blocked_on_ollama.",
    ],
    "M": [
        "Offline A-level: M2 weighted_rrf+extractive Recall 0.5482 (+0.0194 vs M1), nDCG 0.4856 (+0.0493), Tokens 392.8 (-7.4), P95 27.0 ms vs 6.5 ms; quality=Recall 0.5482.",
        "M3 query_adaptive+R0 post is dominated offline: Recall 0.4452 (-0.0836), nDCG 0.3036, Tokens 350.8, P95 9.5 ms; filter/decay/MMR may remove evidence, but per-stage effects were not logged.",
        "cross_encoder rerank fell back (sentence_transformers missing); M2's gain is not evidence of real rerank. B-level blocked_on_ollama.",
    ],
    "U": [
        "Offline A-level: U1/U2/U3 all Recall 0.5927, nDCG 0.4061; Tokens 363.6; P95 42.0/54.5/6.0 ms; quality=Recall 0.5927.",
        "C state benchmark (17 items): U1 item mean 0.3431, U2/U3 0.3627; valid-set exact 0.2353; offline_slot trades ACTIVE (0.4762->0.3333) for HISTORICAL (0->0.3846). P(A|S=1) remains not_available because the benchmark is not paired with answer_f1.",
        "answer_f1 ~0.021-0.022 is offline extractive, not LLM answer quality; B-level blocked_on_ollama.",
    ],
    "K": [
        "Offline store-level: K3 archive 90d lowers staleness 0.2234 vs 0.2314 (K1), lowers contradiction 0.4000 vs 0.4224, raises update_correctness 0.8086 vs 0.7914; quality=update_correctness 0.8086, Tokens not_available, P95 not_available.",
        "K3 removes 490.8 units (K1 0); K2 dedupe removes 8.5 and barely changes metrics; no answer-level F1/recall was measured for K.",
        "K metrics are store-level and repeated per question; no long-term F1 claim; B-level blocked.",
    ],
}

STAGE_TEMPLATES = {
    "W": [
        ("extract", "Write extractor: legacy_flat vs meta_schema", "field_completeness"),
        ("resolve", "Write resolver: append vs mem0_4action", None),
        ("audit", "Write auditor: none vs llm_audit", None),
        ("store", "Store build: units/facts/edges", "graph_edges"),
        ("answer", "R->M->U answer metrics", "answer_f1"),
    ],
    "S": [
        ("build", "Build store units", "graph_nodes"),
        ("graph", "Build graph representation", "graph_edges"),
        ("retrieve", "Retrieval over representation", "evidence_recall"),
        ("answer", "R->M->U answer metrics", "answer_f1"),
    ],
    "R": [
        ("analyze", "Query analyzer (rule)", None),
        ("plan", "Planner nodes", "plan_nodes"),
        ("channels", "Retrieval channels", "channels"),
        ("merge", "Round-robin merge into candidates", "candidates"),
        ("answer", "M->U answer metrics", "answer_f1"),
    ],
    "M": [
        ("raw_channels", "Per-channel candidates", "candidates"),
        ("fusion", "Fusion: rrf / weighted_rrf / query_adaptive", "ndcg"),
        ("rerank", "Rerank: none / cross_encoder (fallback)", None),
        ("mmr", "MMR: none / mmr", "redundancy"),
        ("decay", "Decay: none / time_decay", None),
        ("compress", "Compress: none / extractive", "tokens"),
        ("answer", "Answer metrics", "answer_f1"),
    ],
    "U": [
        ("state", "State resolver: none / offline_slot", "state_accuracy"),
        ("context", "Context format: valid / superseded / conflicts", None),
        ("answer", "Answerer: direct / valid_history / evidence_chain", "answer_f1"),
        ("verify", "Citation/refusal checks", "citations"),
    ],
    "K": [
        ("scan", "Contradiction/duplicate scan", "contradiction_rate"),
        ("maintain", "Maintenance action (dedupe/archive)", "removed"),
        ("store", "Store-level state after maintenance", "units"),
    ],
}


def fmt(x, digits=4):
    if x is None:
        return "not_available"
    return f"{float(x):.{digits}f}"


def three_piece_claim(claim, quality_label, quality_value, tokens, p95):
    q = f"{quality_label}={fmt(quality_value)}"
    t = f"Tokens={tokens:.1f}" if tokens is not None else "Tokens=not_available"
    p = f"P95={p95:.1f} ms" if p95 is not None else "P95=not_available"
    return f"{claim} | quality {q}; {t}; {p}."


MODULE_FAKES = {
    "W": ["schema.params.evidence (accepted but unread)", "schema.params.fields 6 vs 12 (BM25 lexical artifact)",
          "planner.params.k (never read)", "graph channel (S1/S2/S3 identical recall)"],
    "S": ["graph channel (S1/S2/S3 identical recall)", "graph.retrieval.params.max_neighbors (wired but flat)",
          "graph.retrieval.impl (not read; no-op axes)"],
    "R": ["planner.params.k (never read)", "planner.params.analyzer=llm (rule fallback)",
          "retrieval.k is live after C's executor fix (not a no-op)"],
    "M": ["post.mmr x decay interaction (not tested)", "rerank cross_encoder (fallback)",
          "rerank.params.top_n (fallback)"],
    "U": ["state_accuracy available on 17 items but not paired with answer_f1", "query_llm state resolver (not run)"],
    "K": ["store-level metrics repeated per question", "no answer-level F1/recall"],
}
E2_FAKES = ["P(A|C=1) has only 2/2880 questions", "state_accuracy available on 17 items but not paired with answer_f1",
            "Oracle executor/interventions not implemented", "K has no answer-level rows"]
E5_FAKES = ["state_accuracy not recorded", "offline extractive only; no LLM Judge"]
STATE_ACC = {
    "source": "eval/archive/state-accuracy.json",
    "benchmark": "eval/state_benchmark.json",
    "items": 17,
    "as_of_items": 6,
    "candidates": {
        "U1-none-direct": {"item_mean": 0.3431, "pooled_memory": 0.2941, "valid_set_exact": 0.2353,
                           "evidence_recall": 0.5294, "active_acc": 0.4762, "historical_acc": 0.0},
        "U2-offline-valid": {"item_mean": 0.3627, "pooled_memory": 0.3529, "valid_set_exact": 0.2353,
                             "evidence_recall": 0.5294, "active_acc": 0.3333, "historical_acc": 0.3846},
        "U3-offline-chain": {"item_mean": 0.3627, "pooled_memory": 0.3529, "valid_set_exact": 0.2353,
                             "evidence_recall": 0.5294, "active_acc": 0.3333, "historical_acc": 0.3846},
    },
    "P_A_given_S": None,
    "P_A_given_S_reason": "state benchmark items are not paired with answer_f1; no joined (A,S) table.",
}

PARAM_FAKES = ["planner.params.k (never read)", "schema.params.evidence (accepted but unread)",
               "post.mmr x decay interaction (not tested)", "graph channel (S1/S2/S3 no unique hits)",
               "rerank cross_encoder / top_n (fallback)", "P3 seed-17 / P4 order (cancelled)"]


def coverage_limits(offline_rows, fake_factors, source, online_status="pending", extra_na=None):
    na = ["state_accuracy", "judge_accuracy", "oracle_gap", "llm_attribution"]
    if extra_na:
        na = list(dict.fromkeys(na + extra_na))
    return {
        "data_modes": [
            {"mode": "offline", "rows": offline_rows, "source": source, "status": "complete"},
            {"mode": "online", "rows": 0, "source": None, "status": online_status,
             "reason": "Online/B-level run is executing in a separate session; no online rows are mixed into this report."},
        ],
        "fake_factors": fake_factors,
        "a_level_only": True,
        "a_level_note": "Only A-level interface metrics (Recall/nDCG/tokens/P95); answer_f1 is offline extractive; no LLM Judge/B-level.",
        "not_available": na,
        "summary_zh": (f"离线 {offline_rows} 行 / 在线 0 行（{online_status}）；"
                       f"假因子 {len(fake_factors)} 项；仅 A 级接口指标，不是 B 级/LLM 结论。"),
    }


def tp(tokens, p95):
    t = f"Tokens {tokens:.1f}" if tokens is not None else "Tokens not_available"
    p = f"P95 {p95:.1f} ms" if p95 is not None else "P95 not_available"
    return t, p


def percentile(values, p):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    k = max(0, min(len(values) - 1, math.ceil(p / 100 * len(values)) - 1))
    return values[k]


def paired_bootstrap(base_runs, cand_runs, metric, n_boot=2000, seed=2026):
    base = {}
    cand = {}
    for run in base_runs:
        for qid, q in C.qmetrics[run["run_id"]].items():
            if q.get(metric) is not None:
                base[(run["factors"]["seed"], qid)] = float(q[metric])
    for run in cand_runs:
        for qid, q in C.qmetrics[run["run_id"]].items():
            if q.get(metric) is not None:
                cand[(run["factors"]["seed"], qid)] = float(q[metric])
    keys = sorted(set(base) & set(cand))
    deltas = [cand[k] - base[k] for k in keys]
    if len(deltas) < 10:
        return {"delta": round(statistics.mean(deltas), 4) if deltas else None,
                "ci95": None, "paired": True, "significant": None, "pairs": len(deltas),
                "reason": "too few paired questions for bootstrap"}
    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        sample = [deltas[rng.randrange(len(deltas))] for _ in range(len(deltas))]
        boots.append(statistics.mean(sample))
    boots.sort()
    lo = boots[int(0.025 * len(boots))]
    hi = boots[int(0.975 * len(boots)) - 1]
    return {"delta": round(statistics.mean(deltas), 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "paired": True,
            "significant": bool(lo > 0 or hi < 0),
            "pairs": len(deltas),
            "bootstrap_samples": n_boot}


def stage_waterfall(module, by_candidate):
    stages = []
    baseline = MODULE_META[module]["baseline"]
    base_metrics = by_candidate[baseline]["metrics"]
    for stage, desc, metric in STAGE_TEMPLATES[module]:
        entry = {"stage": stage, "description": desc, "available": False, "ms": None, "metrics": {}}
        if metric and base_metrics.get(metric) is not None:
            entry["available"] = True
            entry["metrics"][metric] = base_metrics[metric]
        if stage == "rerank":
            entry["available"] = False
            entry["reason"] = "cross_encoder fell back: sentence_transformers is not installed; no real rerank was applied."
        elif stage == "decay" and module == "M":
            entry["available"] = False
            entry["reason"] = "M1/M2 do not enable decay; M3 inherits R0 time_decay. No per-stage decay metric was logged."
        elif stage == "mmr" and module == "M":
            entry["available"] = base_metrics.get("redundancy") is not None
            entry["reason"] = "redundancy is the only MMR proxy; no per-stage nDCG."
        elif stage in ("state",) and module == "U":
            entry["available"] = False
            entry["reason"] = "state_accuracy is not recorded (0 rows in DB)."
        elif stage == "answer" and module == "K":
            entry["available"] = False
            entry["reason"] = "K runs are store-level only; no answer_f1/recall rows."
        if stage == "answer" and base_metrics.get("p95_latency_ms") is not None:
            entry["ms"] = base_metrics["p95_latency_ms"]
        stages.append(entry)
    return stages


def conversion_public(rows):
    summary = C.conversion_summary(rows)
    out = {}
    for key, value in summary.items():
        item = dict(value)
        if key == "P(A|S=1)":
            item["value"] = None
            item["status"] = "not_available"
            item["reason"] = "state_accuracy is not recorded in runs/s6/e1.sqlite (0 rows)."
        elif key == "P(A|C=1)":
            if item["denominator"] < 30:
                item["observed_value"] = item["value"]
                item["value"] = None
                item["status"] = "insufficient_sample"
                item["reason"] = f"strict C=1 (context_precision>=1.0) has only {item['denominator']} questions; too few for a rate."
            else:
                item["status"] = "ok"
        else:
            item["status"] = "ok"
        out[key] = item
    return out


def make_report(module):
    meta = MODULE_META[module]
    groups, summaries, by_candidate = C.module_report(module)
    baseline = meta["baseline"]
    baseline_runs = groups[baseline]
    quality = meta["quality"]

    comparisons = []
    for candidate, cand_runs in groups.items():
        if candidate == baseline:
            continue
        metrics = (["update_correctness", "staleness", "contradiction_rate", "removed"]
                   if module == "K" else [quality, "ndcg", "tokens", "p95_latency_ms"])
        for metric in metrics:
            b = by_candidate[baseline]["metrics"].get(metric)
            c = by_candidate[candidate]["metrics"].get(metric)
            if b is None or c is None:
                continue
            if module == "K":
                comparisons.append({
                    "baseline": baseline,
                    "candidate": candidate,
                    "metric": metric,
                    "baseline_value": b,
                    "candidate_value": c,
                    "delta": round(c - b, 4),
                    "ci95": None,
                    "paired": False,
                    "significant": None,
                    "pairs": None,
                    "note": "Store-level metrics repeated per question; no per-question independence, so no CI.",
                })
            else:
                bs = paired_bootstrap(baseline_runs, cand_runs, metric)
                comparisons.append({
                    "baseline": baseline,
                    "candidate": candidate,
                    "metric": metric,
                    "baseline_value": b,
                    "candidate_value": c,
                    "delta": round(c - b, 4),
                    "ci95": bs.get("ci95"),
                    "paired": True,
                    "significant": bs.get("significant"),
                    "pairs": bs.get("pairs"),
                    "note": "Descriptive offline bootstrap over paired questions; not a causal test.",
                })

    all_runs = [r for r in summaries.values() for r in r]
    result_metrics = C.mean_metrics(all_runs, meta["metrics"])
    if module == "K":
        result_metrics["tokens"] = None
        result_metrics["p95_latency_ms"] = None

    run_rows = []
    for candidate, items in summaries.items():
        for item in items:
            m = item["metrics"]
            run_rows.append({
                "run_id": item["run_id"],
                "candidate": candidate,
                "seed": item["seed"],
                "sample": "conv-26, conv-30, conv-43, conv-44",
                "question": f"{item['questions']} q · conv-26, conv-30, conv-43, conv-44 · seed {item['seed']}",
                "tokens": m.get("tokens"),
                "latency_ms": m.get("p95_latency_ms"),
                "candidates": m.get("candidates"),
                "answer": ("store-level metrics only; no answer F1" if module == "K"
                           else f"offline extractive; F1={fmt(m.get('answer_f1'))}"),
                "config_hash": item["config_hash"],
                "metrics": m,
            })

    coverage = coverage_limits(len(run_rows), MODULE_FAKES[module],
                               "runs/s6/e1.sqlite")
    if module == "U":
        coverage["not_available"] = ["judge_accuracy", "P(A|S) answer-state pairing",
                                     "oracle_gap", "llm_attribution"]
    by_seed = []
    for candidate, items in summaries.items():
        for seed in (13, 17):
            sub = [it for it in items if it["seed"] == seed]
            if sub:
                by_seed.append({"candidate": candidate, "seed": seed,
                                "metrics": C.mean_metrics(sub, meta["metrics"])})

    pareto = []
    for candidate, item in by_candidate.items():
        m = item["metrics"]
        if module == "K":
            # lower staleness/contradiction better; higher update correctness better
            pareto.append({"candidate": candidate,
                           "quality": m.get("update_correctness"),
                           "cost_tokens": None,
                           "p95_latency_ms": None,
                           "staleness": m.get("staleness"),
                           "contradiction_rate": m.get("contradiction_rate")})
        else:
            pareto.append({"candidate": candidate,
                           "quality": m.get(quality),
                           "cost_tokens": m.get("tokens"),
                           "p95_latency_ms": m.get("p95_latency_ms")})

    tokens_all = result_metrics.get("tokens")
    p95_all = result_metrics.get("p95_latency_ms")
    t, p = tp(tokens_all, p95_all)
    claims = [three_piece_claim(c, meta["quality_label"], result_metrics.get(quality), tokens_all, p95_all)
              for c in MODULE_CLAIMS[module]]
    claims.append(f"Module aggregate over {len(all_runs)} runs: quality ({meta['quality_label']}) = {fmt(result_metrics.get(quality))}, {t}, {p}.")

    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": meta["report_id"],
        "created_at": NOW,
        "manifest": {
            "git_commit": HEAD,
            "data_git_commit": DATA_COMMIT,
            "config_hashes": {c: items[0]["config_hash"] for c, items in summaries.items()},
            "dataset_hash": "sha256:79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4",
            "model": {"llm": "offline-extractive", "embedding": "offline-hash", "judge": "not_run"},
            "offline": True,
            "data_mode": "offline",
            "source_db": "runs/s6/e1.sqlite",
            "source_archive": "eval/archive/s6-e1-screening.json",
        },
        "dataset": {
            "split": "development",
            "samples": ["conv-26", "conv-30", "conv-43", "conv-44"],
            "questions_per_seed": 80,
            "runs": len(all_runs),
            "questions": len(all_runs) * 80,
            "seeds": [13, 17],
            "test_only": False,
        },
        "results": {
            "runs": run_rows,
            "metrics": result_metrics,
            "state_accuracy": STATE_ACC if module == "U" else None,
            "by_candidate": by_candidate,
            "source": {"db": "runs/s6/e1.sqlite", "archive": "eval/archive/s6-e1-screening.json"},
            "error_rate": 0.0,
        },
        "comparisons": comparisons,
        "analysis": {
            "main_effects": [
                {"factor": "candidate", "levels": list(by_candidate),
                 "metrics": {c: v["metrics"] for c, v in by_candidate.items()}}
            ],
            "interactions": [],
            "pareto": pareto,
            "by_seed": by_seed,
            "stage_waterfall": stage_waterfall(module, by_candidate),
            "failure_breakdown": [],
            "failure_note": "0 errors across 36 S6 runs; no failure taxonomy to report.",
            "conversion": {
                "definitions": {
                    "A": "answer_f1 > 0 (offline extractive)",
                    "R": "evidence_recall >= 1.0",
                    "C": "context_precision >= 1.0 (strict: no distractors)",
                    "S": "state_accuracy >= 1.0 (not recorded)",
                },
                "module": conversion_public(C.conversion_block(module)),
                "global_answer_modules": conversion_public(
                    [q for run in C.runs if run["factors"]["module"] != "K"
                     for q in C.qmetrics[run["run_id"]].values()]),
            },
            "bootstrap": {"samples": 2000, "seed": 2026, "paired_by": "seed+qid",
                          "note": "Percentile bootstrap; descriptive only."},
            "coverage_limits": coverage,
            "state_accuracy": STATE_ACC if module == "U" else None,
        },
        "coverage_limits": coverage,
        "conclusion": {
            "status": "partial",
            "three_piece": {
                "quality": {"metric": meta["quality_label"], "value": result_metrics.get(quality)},
                "tokens_per_query": tokens_all,
                "p95_latency_ms": p95_all,
            },
            "claims": claims,
            "conditions": [
                "Offline A-level only: hashing embedding + extractive answer; no LLM was called.",
                "Development split (conv-26/30/43/44), 80 questions/seed, seeds 13/17.",
                "One module is varied at a time; other modules are fixed at the S6 reference settings.",
            ],
            "limitations": [
                "answer_f1 is offline extractive, not an LLM F1; Judge is not_run.",
                "P95 is runner-reported per-question seconds; it is not an API/local-GPU deployment latency.",
                "cross_encoder rerank fell back because sentence-transformers is not installed.",
                "state_accuracy is not recorded, so P(A|S=1) is not_available.",
                "Paired bootstrap is descriptive; two seeds do not support a formal causal claim.",
            ],
            "next_actions": [
                "Run the same candidates with --online --judge when an API/Ollama endpoint is available.",
                "Record state_accuracy and judge_accuracy before claiming U/state gains.",
                "Install sentence-transformers or add an API rerank adapter before interpreting M2 rerank.",
            ],
        },
        "online": online_pointer(meta["report_id"]),
        "web": {"route": f"#/experiments/{meta['report_id']}", "published": True},
        "coverage": {"catalog_rows": meta["covers"], "note": "This S6 module screen partially covers these catalog rows; see catalog for exact status."},
    }
    return report


def write(report):
    path = REPORT_DIR / f"{report['experiment_id']}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _enrich_s7b_runs(rows, archive_by_id):
    out = []
    for row in rows:
        item = archive_by_id.get(row["run_id"], {})
        m = item.get("metrics", {})
        p95 = m.get("p95_seconds")
        enriched = dict(row)
        enriched.update({
            "question": f"{row.get('n_questions')} q · {row.get('candidate')} · seed {row.get('seed')}",
            "tokens": m.get("tokens"),
            "latency_ms": round(p95 * 1000, 3) if p95 is not None else None,
            "candidates": m.get("candidates"),
            "answer": (f"offline; P(A|R=1)={row.get('p_outcome_given_gate')}" if row.get("n_gated")
                       else "store-level only; no gate/answer rows"),
        })
        out.append(enriched)
    return out


def build_e2():
    s7b = C.s7b
    by_module = {row["module"]: row for row in s7b["by_module"]}
    by_candidate = s7b["by_candidate"]
    by_seed = {row["seed"]: row for row in s7b["by_seed"]}
    archive_by_id = {}
    for items in C.archive["modules"].values():
        for item in items:
            archive_by_id[item["run_id"]] = item
    answer_runs = [r for r in s7b["runs"] if r.get("n_gated", 0) > 0]
    tokens = [a["mean_outcome"] for a in answer_runs]
    # token/p95 from S6 archive for answer modules
    answer_archive = [it for mod in ("W", "S", "R", "M", "U") for it in C.archive["modules"][mod]]
    avg_tokens = round(statistics.mean(it["metrics"]["tokens"] for it in answer_archive), 3)
    avg_p95 = round(statistics.mean(it["metrics"]["p95_seconds"] * 1000 for it in answer_archive), 3)
    global_conv = C.conversion_summary(
        [q for run in C.runs if run["factors"]["module"] != "K" for q in C.qmetrics[run["run_id"]].values()])
    global_conv_public = conversion_public(
        [q for run in C.runs if run["factors"]["module"] != "K" for q in C.qmetrics[run["run_id"]].values()])
    module_rows = []
    for mod in ("W", "S", "R", "M", "U", "K"):
        row = by_module[mod]
        module_rows.append({
            "module": mod,
            "runs": row["runs"],
            "runs_with_gate": row["runs_with_gate"],
            "n_observed": row["n_observed"],
            "n_gated": row["n_gated"],
            "p_gate": row["p_gate"],
            "p_outcome": row["p_outcome"],
            "p_outcome_given_gate": row["p_outcome_given_gate"],
            "lift": row["lift_mean"],
            "conversion_run_min": row["conversion_run_min"],
            "conversion_run_max": row["conversion_run_max"],
        })
    claims = [
        f"Offline A-level: P(A|R=1)={fmt(global_conv['P(A|R=1)']['value'])} (n={global_conv['P(A|R=1)']['denominator']}) vs P(A)={fmt(global_conv['P(A)']['value'])} across 30 answer-capable runs; lift={fmt((global_conv['P(A|R=1)']['value'] or 0)-(global_conv['P(A)']['value'] or 0))}; quality=P(A|R=1), Tokens {avg_tokens:.1f}, P95 {avg_p95:.1f} ms.",
        "By module P(A|R=1): M 0.2525 > R 0.2330 > U 0.1687 > S 0.1449 > W 0.1429; all module lifts vs P(A) are negative offline (M -0.0505, R -0.0502, U -0.0387, S -0.0438, W -0.0599).",
        "P(A|C=1) is not_available: strict C=1 has only 2/2880 questions. P(A|S=1) is not_available: C state benchmark gives P(S=1)=0.3431/0.3627/0.3627 for U1/U2/U3 but has no matched answer_f1 pairs. Do not read these as no effect.",
    ]
    claims = [three_piece_claim(c, "P(A|R=1)", global_conv["P(A|R=1)"]["value"], avg_tokens, avg_p95)
              for c in claims]
    e2_coverage = coverage_limits(36, E2_FAKES, "runs/s6/e1.sqlite")
    e2_coverage["not_available"] = ["judge_accuracy", "P(A|S) answer-state pairing",
                                    "oracle_gap", "llm_attribution"]
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": "E2-1",
        "created_at": NOW,
        "manifest": {
            "git_commit": HEAD,
            "data_git_commit": "4fc1571",
            "config_hashes": {},
            "model": {"llm": "offline-extractive", "embedding": "offline-hash", "judge": "not_run"},
            "offline": True,
            "data_mode": "offline",
            "source_db": "runs/s6/e1.sqlite",
            "source_archive": "eval/archive/s7b-a-offline.json",
        },
        "dataset": {
            "split": "development",
            "samples": ["conv-26", "conv-30", "conv-43", "conv-44"],
            "questions": 2400,
            "seeds": [13, 17],
            "test_only": False,
        },
        "results": {
            "runs": _enrich_s7b_runs(s7b["runs"], archive_by_id),
            "metrics": {
                "P(A)": global_conv["P(A)"]["value"],
                "P(R)": global_conv["P(R)"]["value"],
                "P(A|R=1)": global_conv["P(A|R=1)"]["value"],
                "P(A|C=1)": None,
                "P(A|S=1)": None,
                "P(S=1)": {"U1": 0.3431, "U2": 0.3627, "U3": 0.3627},
                "tokens": avg_tokens,
                "p95_latency_ms": avg_p95,
                "error_rate": 0.0,
            },
            "gate_availability": s7b["gate_availability"],
            "state_accuracy": STATE_ACC,
            "source": {"db": "runs/s6/e1.sqlite", "archive": "eval/archive/s7b-a-offline.json"},
        },
        "comparisons": [
            {"baseline": "P(A)", "candidate": "P(A|R=1)", "metric": "conversion",
             "baseline_value": global_conv["P(A)"]["value"],
             "candidate_value": global_conv["P(A|R=1)"]["value"],
             "delta": round((global_conv["P(A|R=1)"]["value"] or 0) - (global_conv["P(A)"]["value"] or 0), 4),
             "ci95": None, "paired": False, "significant": None,
             "note": "Descriptive conversion; denominator changes, so this is not a paired effect."},
        ],
        "analysis": {
            "main_effects": [],
            "interactions": [],
            "pareto": [],
            "by_module": module_rows,
            "by_candidate": by_candidate,
            "by_seed": s7b["by_seed"],
            "stage_waterfall": [
                {"stage": "raw_channels", "available": True, "ms": None,
                 "metrics": {"candidates": 15.0, "channels": 2.0}},
                {"stage": "fusion", "available": True, "ms": None,
                 "metrics": {"ndcg": 0.4363, "evidence_recall": 0.5288},
                 "note": "M1 rrf baseline; post-fusion metrics are measured at answer time."},
                {"stage": "rerank", "available": False, "ms": None, "reason": "cross_encoder fell back (sentence_transformers missing)."},
                {"stage": "mmr", "available": True, "ms": None, "metrics": {"redundancy": 0.0508},
                 "note": "redundancy is the only MMR proxy; no per-stage nDCG."},
                {"stage": "decay", "available": False, "ms": None, "reason": "M1 does not enable decay; no per-stage decay metric."},
                {"stage": "compress", "available": True, "ms": None, "metrics": {"tokens": 400.2},
                 "note": "M1 has no compression; token value is the M1 context size."},
                {"stage": "answer", "available": True, "ms": 6.5,
                 "metrics": {"answer_f1": 0.0468, "evidence_recall": 0.5288}},
            ],
            "failure_breakdown": [],
            "failure_note": "0 errors across 36 S6 runs; no failure taxonomy.",
            "conversion": {
                "definitions": {
                    "A": "answer_f1 > 0 (offline extractive)",
                    "R": "evidence_recall >= 1.0",
                    "C": "context_precision >= 1.0 (strict)",
                    "S": "state_accuracy >= 1.0 (not recorded)",
                },
                "global_answer_modules": global_conv_public,
                "by_module": module_rows,
            },
            "coverage_limits": e2_coverage,
            "state_accuracy": STATE_ACC,
            "oracle_gap": s7b["oracle_gap"],
            "llm_attribution": s7b["llm_attribution"],
        },
        "conclusion": {
            "status": "partial",
            "three_piece": {
                "quality": {"metric": "P(A|R=1)", "value": global_conv["P(A|R=1)"]["value"]},
                "tokens_per_query": avg_tokens,
                "p95_latency_ms": avg_p95,
            },
            "claims": claims,
            "conditions": [
                "Offline A-level conversion over S6 runs; no LLM, no Oracle run.",
                "Gate R=1 is evidence_recall>=1.0; outcome A=1 is answer_f1>0 (offline extractive).",
                "Development split; 36 runs across six modules and two seeds.",
            ],
            "limitations": [
                "Negative lift is confounded by the offline extractive answerer; it is not evidence that retrieval harms answers.",
                "P(A|C=1) has only 2/2880 C=1 questions; P(A|S=1) has 0 state_accuracy rows -> not_available.",
                "oracle_gap and llm_attribution are not_available (no Oracle run / no LLM comparison).",
                "K has no answer-level rows; K is excluded from conversion.",
                "Two seeds; seed 13 0.2439 vs seed 17 0.1240 shows large dispersion.",
            ],
            "next_actions": [
                "Add an Oracle executor/run and a retrieval-ceiling metric before S7b-B.",
                "Record state_accuracy and judge_accuracy in the runner.",
                "Re-run online with a real LLM and compare conversion; keep offline numbers separate.",
            ],
        },
        "coverage_limits": e2_coverage,
        "online": online_pointer("E2-1"),
        "web": {"route": "#/experiments/E2-1", "published": True},
        "coverage": {"catalog_rows": ["E2-1"], "note": "A-level conversion only; Oracle/LLM attribution remain missing."},
    }
    return report


def build_e5():
    source = json.loads((ROOT / "reports/experiments/final-w3-test-offline.json").read_text())
    for row in source["results"]["runs"]:
        m = row.get("metrics", {})
        row["question"] = f"{m.get('questions')} q · {row.get('sample')} · seed {row.get('seed')}"
        row["tokens"] = m.get("tokens")
        row["latency_ms"] = m.get("p95_latency_ms")
        row["candidates"] = None
        row["answer"] = f"offline extractive; F1={fmt(m.get('answer_f1'))}"
    b = source["results"]["baseline_metrics"]
    c = source["results"]["metrics"]
    claims = [
        f"Offline test (conv-41/42): B0 F1={fmt(b['answer_f1'])}, Recall={fmt(b['evidence_recall'])}, Tokens={b['tokens']:.1f}, P95={b['p95_latency_ms']:.1f} ms; R0 F1={fmt(c['answer_f1'])}, Recall={fmt(c['evidence_recall'])}, Tokens={c['tokens']:.1f}, P95={c['p95_latency_ms']:.1f} ms.",
        "R0 is worse than B0 offline: answer_f1 delta -0.0300 (paired bootstrap 95% CI [-0.0575, -0.0104]); evidence_recall delta -0.1417 (CI [-0.3268, -0.0066]).",
        "This is a test-split offline result, not an LLM-quality or final deployment conclusion; B-level and state_accuracy are not_available.",
        "Second Judge and human kappa are not_run; only B0/R0, test conv-41/conv-42, seeds 13/17.",
    ]
    # E5 claims are curated; append the B0/R0 three-piece explicitly.
    claims = [
        f"{claim} | quality F1 B0={fmt(b['answer_f1'])} / R0={fmt(c['answer_f1'])}; Tokens B0={b['tokens']:.1f} / R0={c['tokens']:.1f}; P95 B0={b['p95_latency_ms']:.1f} ms / R0={c['p95_latency_ms']:.1f} ms."
        for claim in claims
    ]
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": "E5-1",
        "created_at": NOW,
        "manifest": {
            "git_commit": HEAD,
            "data_git_commit": "ac4dec9",
            "config_hashes": source["manifest"].get("config_hashes", {}),
            "model": source["manifest"].get("model", {}),
            "offline": True,
            "data_mode": "offline",
            "source": "eval/archive/final-w3.json + eval/archive/experiments/final-w3-test-offline.json",
        },
        "dataset": source["dataset"],
        "results": source["results"],
        "comparisons": source["comparisons"],
        "analysis": {**source["analysis"],
                     "evaluation": {"second_judge": "not_run", "human_kappa": "not_run",
                                    "seeds": [13, 17], "test_samples": ["conv-41", "conv-42"]},
                     "coverage_limits": coverage_limits(8, E5_FAKES, "eval/archive/final-w3.json")},
        "conclusion": {
            "status": "not_supported",
            "three_piece": {
                "quality": {"metric": "answer_f1", "baseline_B0": b["answer_f1"], "candidate_R0": c["answer_f1"]},
                "tokens_per_query": {"B0": b["tokens"], "R0": c["tokens"]},
                "p95_latency_ms": {"B0": b["p95_latency_ms"], "R0": c["p95_latency_ms"]},
            },
            "claims": claims,
            "conditions": [
                "Frozen B0/R0 configs; no test-time tuning.",
                "Test split conv-41/conv-42; stratified questions.",
                "Offline extractive answer + hashing embedding; not an LLM-quality claim.",
            ],
            "limitations": [
                "No real Ollama/API model; F1 is offline extractive.",
                "state_accuracy is not recorded.",
                "Two seeds and 20 questions/sample; bootstrap resamples questions, not conversations.",
            ],
            "next_actions": [
                "Re-run --online with frozen configs when a model endpoint is available.",
                "Add state_accuracy before reporting it.",
            ],
        },
        "coverage_limits": {**coverage_limits(8, E5_FAKES, "eval/archive/final-w3.json"),
                           "not_available": ["state_accuracy", "judge_accuracy", "second_judge",
                                             "human_kappa", "oracle_gap", "llm_attribution"]},
        "online": online_pointer("E5-1", seeds=(13, 17), questions=80,
                                  source="eval/archive/final-w3-test-online.json"),
        "web": {"route": "#/experiments/E5-1", "published": True},
        "coverage": {"catalog_rows": ["E5-1"], "note": "Offline test-only confirmation; online and second-judge checks pending."},
        "source_report": "final-w3-test-offline",
    }
    return report



def build_params():
    base = json.loads((ROOT / "eval/archive/params-curves.json").read_text())
    corrected = [
        json.loads((ROOT / "eval/archive/params-planner-k-corrected.json").read_text()),
        json.loads((ROOT / "eval/archive/params-mmr-lambda-nodecay.json").read_text()),
        json.loads((ROOT / "eval/archive/params-graph-max-neighbors-corrected.json").read_text()),
    ]
    ext = json.loads((ROOT / "eval/archive/e1-params-ext.json").read_text())
    ref = base["factors"][0]["reference_metrics"]
    p95_ref = 5.928  # corrected R4 k=15 reference row
    rows = []
    factors = []
    keep_base = {"schema.params.fields", "post.decay.params.lambda", "post.compress.params.budget_tokens"}
    for f in base["factors"]:
        if f["factor"]["id"] not in keep_base:
            continue
        factors.append({
            "factor": f["factor"]["id"], "module": f["factor"]["module"],
            "levels": f["factor"]["levels"], "verdict": f.get("verdict"),
            "wired": f["factor"].get("wired"), "effective_in_e2e": f.get("effective_in_e2e"),
            "source": "eval/archive/params-curves.json",
        })
        for r in f["rows"]:
            rows.append({"factor": f["factor"]["id"], "module": f["factor"]["module"],
                         "level": r["level_label"], "row": r, "ref": ref,
                         "source": "eval/archive/params-curves.json"})
    for f in corrected:
        factors.append({
            "factor": f["factor"]["id"], "module": f["factor"]["module"],
            "levels": f["factor"]["levels"], "verdict": f.get("verdict"),
            "wired": f["factor"].get("wired"), "effective_in_e2e": f.get("effective_in_e2e"),
            "source": "corrected",
        })
        for r in f["rows"]:
            rows.append({"factor": f["factor"]["id"], "module": f["factor"]["module"],
                         "level": r["level_label"], "row": r,
                         "ref": f.get("reference_metrics", ref), "source": "corrected"})
    for f in ext["factors"]:
        factors.append({
            "factor": f["factor"]["id"], "module": f["factor"]["module"],
            "levels": f["factor"]["levels"], "verdict": f.get("verdict"),
            "wired": f["factor"].get("wired"), "effective_in_e2e": f.get("effective_in_e2e"),
            "source": "eval/archive/e1-params-ext.json",
        })
        for r in f["rows"]:
            rows.append({"factor": f["factor"]["id"], "module": f["factor"]["module"],
                         "level": r["level_label"], "row": r,
                         "ref": f.get("reference_metrics", ref), "source": "eval/archive/e1-params-ext.json"})

    run_rows = []
    comparisons = []
    for item in rows:
        r, fref = item["row"], item["ref"]
        m = {k: r.get(k) for k in ("evidence_recall", "ndcg", "tokens", "redundancy", "context_precision",
                                   "candidates", "p95_latency_ms", "field_completeness", "error_rate")}
        run_rows.append({
            "run_id": r["run_id"], "candidate": f"{item['factor']}={item['level']}",
            "factor": item["factor"], "module": item["module"], "level": item["level"],
            "question": f"{r.get('n_questions')} q · {item['factor']}={item['level']}",
            "tokens": m.get("tokens"), "latency_ms": m.get("p95_latency_ms"),
            "candidates": m.get("candidates"),
            "answer": "offline A-interface; answer F1/Judge intentionally not reported",
            "source": item["source"], "status": r.get("status"),
            "metrics": m,
        })
        for metric in ("evidence_recall", "ndcg", "tokens"):
            base_v = fref.get(metric)
            cand_v = r.get(metric)
            if base_v is None or cand_v is None:
                continue
            comparisons.append({
                "baseline": f"reference ({item['factor']})",
                "candidate": f"{item['factor']}={item['level']}",
                "metric": metric,
                "baseline_value": base_v,
                "candidate_value": cand_v,
                "delta": round(cand_v - base_v, 6),
                "ci95": None, "paired": False, "significant": None,
                "note": "Single-level curve; CI only available where C reported it in the correction tables.",
            })

    claims = [
        "R4 retrieval.k corrected: 10/15/25 Recall 0.4206/0.4619/0.4913, nDCG 0.2638/0.2746/0.2700, Tokens 227.4/344.6/578.9; k=25 recall +0.0295 +234.3 tokens, k=10 recall -0.0417 -117.2 tokens; nDCG n.s.",
        "MMR with decay off: lambda 0.9 vs 0.5 nDCG +0.00236 (95% cluster CI [+0.00098,+0.00417]); recall/tokens unchanged; MMR x decay interaction NOT tested.",
        "max_neighbors is wired (10/40/80) but flat: only 23/240 questions route to graph_khop and the 15-candidate budget saturates; flat is a routing/budget result, not an unwired parameter.",
        "schema.params.evidence is no_op (never read); fields 6 vs 12 is a BM25 lexical artifact; P2 extension: rrf_k 10 vs 60 nDCG +0.0448, filter none vs threshold recall +0.0886 / nDCG +0.0564.",
    ]
    claims = [three_piece_claim(c, "Recall", ref["evidence_recall"], ref["tokens"], p95_ref) for c in claims]
    claims.append(three_piece_claim(
        "P3 seed 17 and P4 order are cancelled; E1-M3 is blocked_on_config because main rejects post.order list and c2-post-order.patch is not merged.",
        "Recall", ref["evidence_recall"], ref["tokens"], p95_ref))
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": "E1-2-params",
        "created_at": NOW,
        "manifest": {
            "git_commit": HEAD,
            "data_git_commit": "2c1e22a",
            "config_hashes": {"reference": base["factors"][0].get("reference_hash")},
            "model": {"llm": "offline-extractive", "embedding": "offline-hash", "judge": "not_run"},
            "offline": True,
            "data_mode": "offline",
            "source_db": "runs/params/p1.sqlite + runs/params/p1-r4.sqlite + runs/params/p1-mmr-nodecay.sqlite + runs/params/p1-maxneighbors.sqlite",
            "source_archive": "eval/archive/params-curves.json + params-*-corrected.json + e1-params-ext.json",
        },
        "dataset": {
            "split": "development",
            "samples": base["dataset"]["samples"],
            "question_limit_per_sample": base["dataset"]["question_limit"],
            "questions_per_level": base["dataset"]["questions_per_level"],
            "runs": len({r["run_id"] for r in run_rows}),
            "levels": len(run_rows),
            "test_only": False,
        },
        "results": {
            "runs": run_rows,
            "metrics": {**ref, "p95_latency_ms": p95_ref, "questions_per_level": base["dataset"]["questions_per_level"],
                        "runs": len({r["run_id"] for r in run_rows}), "error_rate": 0.0},
            "factors": factors,
            "source": {"archive": "params-curves.json + corrected + e1-params-ext.json",
                       "db": "runs/params/*.sqlite"},
        },
        "comparisons": comparisons,
        "analysis": {
            "main_effects": factors,
            "interactions": [],
            "pareto": [],
            "by_factor": factors,
            "corrections": [
                "R4 retrieval.k is live after executor fix; old params-planner-k.json superseded.",
                "MMR lambda is only testable with decay off; reference-r0-nodecay.json.",
                "max_neighbors is wired but flat due to routing/budget, not unconsumed.",
                "schema.params.evidence is a no_op; curve deleted.",
                "P2 extension adds rrf_k and post.filter curves.",
            ],
            "stage_waterfall": [
                {"stage": "raw_channels", "available": True, "ms": None, "metrics": {"candidates": 12.79}},
                {"stage": "fusion", "available": True, "ms": None, "metrics": {"ndcg": 0.2746},
                 "note": "rrf_k 10 vs 60 nDCG +0.0448 (P2)."},
                {"stage": "rerank", "available": False, "ms": None, "reason": "sentence-transformers absent; cross_encoder fallback."},
                {"stage": "mmr", "available": True, "ms": None, "metrics": {"ndcg_decay_off_best": 0.3292},
                 "note": "decay off; MMR x decay interaction not tested."},
                {"stage": "decay", "available": True, "ms": None, "metrics": {"ndcg_best": 0.2873},
                 "note": "decay lambda=0.001 is the only real canonical-order effect."},
                {"stage": "compress", "available": True, "ms": None, "metrics": {"tokens_best": 340.4},
                 "note": "compress 500 saves 4.1 tokens; 1000/2000/4000 identical at this context size."},
                {"stage": "answer", "available": False, "ms": None,
                 "reason": "No answer F1/Judge reported in this A-interface run."},
            ],
            "failure_breakdown": [],
            "failure_note": "0 errors across all corrected runs; flat curves are no-op/routing/fallback, not failures.",
            "coverage_limits": coverage_limits(len(run_rows), PARAM_FAKES, "runs/params/*.sqlite"),
        },
        "conclusion": {
            "status": "partial",
            "three_piece": {"quality": {"metric": "evidence_recall", "value": ref["evidence_recall"]},
                            "tokens_per_query": ref["tokens"], "p95_latency_ms": p95_ref},
            "claims": claims,
            "conditions": [
                "Offline A-level; 4 dev conversations, 60 q/conversation, 240 q/level.",
                "Corrected R4/MMR/max_neighbors artifacts supersede the old params-curves table.",
                "No answer F1, no Judge; interface/curve study only.",
            ],
            "limitations": [
                "Hashing embedding is not semantic.",
                "MMR x decay interaction is not tested; MMR scan fixes decay off.",
                "P3 seed 17 and P4 order are cancelled; do not cite them.",
                "P95 is per-question runner latency, not deployment latency.",
            ],
            "next_actions": [
                "Merge c2-post-order.patch and rerun E1-M3 on main before citing order effects.",
                "Wire planner.params.k or remove it from the spec.",
                "Add a real cross-encoder before M6/top_n conclusions.",
            ],
        },
        "coverage_limits": coverage_limits(len(run_rows), PARAM_FAKES, "runs/params/*.sqlite"),
        "online": online_not_run("E1.2 params are offline A-level only; no online counterpart."),
        "web": {"route": "#/experiments/E1-2-params", "published": True},
        "coverage": {"catalog_rows": ["E1-W4", "E1-S2", "E1-R4", "E1-M4", "E1-M6"],
                     "note": "Corrected E1.2 parameter layer; R4 k live, max_neighbors wired but flat, evidence no_op, MMR decay-off only."},
    }
    return report



def build_r3():
    d = json.loads((ROOT / "eval/archive/e1-r3-graph.json").read_text())
    cells = d["cells"]
    graph_cells = [c for c in cells if c["impl"] != "vector_only"]
    vector_cells = [c for c in cells if c["impl"] == "vector_only"]
    mean_recall = round(sum(c["evidence_recall"] for c in graph_cells) / len(graph_cells), 4)
    mean_ndcg = round(sum(c["ndcg"] for c in graph_cells) / len(graph_cells), 4)
    mean_p95 = round(sum(c["latency_p95_ms"] for c in graph_cells) / len(graph_cells), 3)
    vec_recall = round(sum(c["evidence_recall"] for c in vector_cells) / len(vector_cells), 4)
    vec_ndcg = round(sum(c["ndcg"] for c in vector_cells) / len(vector_cells), 4)
    vec_p95 = round(sum(c["latency_p95_ms"] for c in vector_cells) / len(vector_cells), 3)
    comparisons = []
    for row in d.get("paired_vs_vector_only", []):
        for metric, key in (("evidence_recall", "evidence_recall"), ("ndcg", "ndcg"), ("answer_f1", "answer_f1")):
            delta = row["delta"][key]
            comparisons.append({
                "baseline": "vector_only", "candidate": f"{row['impl']}/{row['repr']}",
                "metric": metric, "baseline_value": None, "candidate_value": None,
                "delta": delta["mean_delta"], "ci95": None, "paired": True, "significant": None,
                "improved": delta["improved"], "worsened": delta["worsened"], "unchanged": delta["unchanged"],
                "note": "Graph dispatch vs vector_only on the same 61 multi-hop questions; no CI in archive.",
            })
    for row in d.get("ppr_vs_entity_subgraph", []):
        for metric, key in (("evidence_recall", "evidence_recall"), ("ndcg", "ndcg"), ("answer_f1", "answer_f1")):
            delta = row["delta"][key]
            comparisons.append({
                "baseline": f"entity_subgraph/{row['repr']}", "candidate": f"ppr/{row['repr']}",
                "metric": metric, "baseline_value": None, "candidate_value": None,
                "delta": delta["mean_delta"], "ci95": None, "paired": True, "significant": None,
                "improved": delta["improved"], "worsened": delta["worsened"], "unchanged": delta["unchanged"],
                "note": "PPR vs entity_subgraph on the same 61 multi-hop questions; no CI in archive.",
            })
    claims = [
        "R3 dispatch 13 configs x 61 multi-hop q offline: graph cells final Recall 0.2372 (vector_only 0.2257); nDCG 0.2334; p95 28.5 ms; quality=Recall 0.2372, Tokens not_available, P95 28.5 ms.",
        "Graph-novel candidates are 34-91 per config, but 0 survive fusion; final recall is insensitive to graph impl/repr. This is a fusion/budget bottleneck, not evidence that graph is useless with a real model.",
        "Offline hash embedding is not semantic; planner.analyzer=llm falls back to rule in every cell; B-level blocked_on_ollama.",
    ]
    claims = [three_piece_claim(c, "Recall", mean_recall, None, mean_p95) for c in claims]
    coverage = coverage_limits(len(cells), ["graph candidates do not survive fusion", "real embedding",
                                            "planner.analyzer=llm falls back to rule"], "runs/r3-graph/r3.sqlite")
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": "E1-R3",
        "created_at": NOW,
        "manifest": {
            "git_commit": HEAD,
            "data_git_commit": "2c1e22a",
            "config_hashes": {c["run_id"]: c["config_hash"] for c in cells},
            "model": {"llm": "offline-extractive", "embedding": "offline-hash", "judge": "not_run"},
            "offline": True,
            "data_mode": "offline",
            "source_db": "runs/r3-graph/r3.sqlite",
            "source_archive": "eval/archive/e1-r3-graph.json",
        },
        "dataset": {
            "split": "development",
            "samples": d["protocol"]["samples"],
            "questions": d["protocol"]["questions_per_config"],
            "configs": len(cells),
            "seeds": [],
            "test_only": False,
            "subset": d["protocol"]["subset"],
        },
        "results": {
            "runs": [{
                "run_id": c["run_id"], "candidate": f"{c['impl']}/{c['repr']}",
                "question": f"{c['n']} multi-hop q · {c['impl']}/{c['repr']}",
                "tokens": None, "latency_ms": c.get("latency_p95_ms"), "candidates": c.get("candidates_mean"),
                "answer": f"offline; F1={fmt(c.get('answer_f1'))}",
                "metrics": c,
            } for c in cells],
            "metrics": {"evidence_recall": mean_recall, "ndcg": mean_ndcg,
                        "multi_hop_recall": round(sum(c["multi_hop_recall"] for c in graph_cells) / len(graph_cells), 4),
                        "answer_f1": round(sum(c["answer_f1"] for c in graph_cells) / len(graph_cells), 4),
                        "tokens": None, "p95_latency_ms": mean_p95, "error_rate": 0.0,
                        "questions": d["protocol"]["questions_per_config"],
                        "vector_only": {"evidence_recall": vec_recall, "ndcg": vec_ndcg, "p95_latency_ms": vec_p95}},
            "cells": cells,
            "source": {"db": "runs/r3-graph/r3.sqlite", "archive": "eval/archive/e1-r3-graph.json"},
        },
        "comparisons": comparisons,
        "analysis": {
            "main_effects": [], "interactions": [], "pareto": [],
            "by_impl": cells,
            "paired_vs_vector_only": d.get("paired_vs_vector_only", []),
            "ppr_vs_entity_subgraph": d.get("ppr_vs_entity_subgraph", []),
            "graph_channel_survival": d.get("graph_channel_survival", []),
            "stage_waterfall": [
                {"stage": "graph_candidates", "available": True, "ms": None,
                 "metrics": {"graph_novel_candidates": "34-91"}},
                {"stage": "fusion", "available": True, "ms": None,
                 "metrics": {"graph_novel_in_final": 0}, "note": "graph-only candidates are dropped by fusion/budget."},
                {"stage": "retrieve", "available": True, "ms": None,
                 "metrics": {"evidence_recall": 0.2372}},
                {"stage": "answer", "available": True, "ms": mean_p95,
                 "metrics": {"answer_f1": round(sum(c["answer_f1"] for c in cells) / len(cells), 4)}},
            ],
            "failure_breakdown": [],
            "failure_note": "0 error rows across 13 configs; flat recall is a fusion/graph-survival result.",
            "coverage_limits": coverage,
        },
        "conclusion": {
            "status": "partial",
            "three_piece": {"quality": {"metric": "evidence_recall", "value": mean_recall},
                            "tokens_per_query": None, "p95_latency_ms": mean_p95},
            "claims": claims,
            "conditions": [
                "Offline A-level; LoCoMo category=1 multi-hop subset, 61 questions/config.",
                "13 configs: 4 graph impls x 3 graph reprs + vector_only references.",
                "No answer F1/Judge; B-level blocked.",
            ],
            "limitations": [
                "dual_channel is approximate (undirected, untyped edges; semantic channel is BM25).",
                "Offline hash embedding is not semantic.",
                "Graph-only candidates 0 survive fusion, so final recall cannot distinguish graph impl/repr.",
                "planner.analyzer=llm falls back to rule in every cell.",
            ],
            "next_actions": [
                "Test fusion policies that preserve graph-only candidates.",
                "Re-run with a real embedding / typed entity channels.",
                "Add B-level F1/Judge before claiming graph value.",
            ],
        },
        "coverage_limits": coverage,
        "online": online_not_run("R3 graph dispatch is offline only; A's online S6 18-run archive has no R3 cells."),
        "web": {"route": "#/experiments/E1-R3", "published": True},
        "coverage": {"catalog_rows": ["E1-R3", "E1-S2"],
                     "note": "Graph retrieval dispatch; final recall flat because graph candidates do not survive fusion."},
    }
    return report


def main():
    paths = []
    for module in MODULE_META:
        report = make_report(module)
        paths.append(write(report))
    paths.append(write(build_e2()))
    paths.append(write(build_e5()))
    paths.append(write(build_params()))
    paths.append(write(build_r3()))
    summary = {
        "created_at": NOW,
        "reports": [str(p.relative_to(ROOT)) for p in paths],
        "data_mode": "offline",
        "note": "Offline-only reports; online fields are pending and must not be filled with these numbers.",
    }
    (HERE / "offline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(str(p) for p in paths))


if __name__ == "__main__":
    main()
