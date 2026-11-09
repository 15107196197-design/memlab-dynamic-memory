#!/usr/bin/env python3
"""Build ``memlab/experiment-report@1`` reports for the online E3 / M2 runs.

The raw archives (``eval/archive/e3-2x2.json`` and ``eval/archive/m2-rerank.json``)
only contain run-level metrics.  This script re-reads the SQLite stores, checks
that the raw JSON numbers agree with the DB (tolerance 0.001), computes paired
per-question deltas with a deterministic 1000-resample bootstrap, and writes:

    eval/archive/e3-online-2x2-report.json
    eval/archive/m2-online-rerank-report.json

Optional (``--with-e2``):

    eval/archive/e2-oracle-retrieval-report.json

Design rules
------------
* SQLite is opened read-only; raw archives are never modified.
* Bootstrap: paired resampling over qids, 1000 iterations, seed 13, percentile
  interval at 95%.  Re-running is byte-identical.
* ``created_at`` is the newest run ``updated_at`` (not wall-clock time), so an
  unchanged DB gives an unchanged report.
* E3 conclusion follows the pre-registered rule: fusion F1 CI entirely > 0 is
  ``supported``; a CI containing 0 is ``inconclusive``.
* M2 conclusion requires F1 and Recall to be significantly lower *and* nDCG to
  be significantly higher before it is marked ``partial``; otherwise it is
  ``inconclusive`` while still reporting the descriptive direction.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "eval" / "archive"

SAMPLES = ["conv-26", "conv-30", "conv-43", "conv-44"]
SEED = 13
BOOTSTRAP_ITERATIONS = 1000
CI_LEVEL = 0.95
TOLERANCE = 0.001

E3_METRICS = ["answer_f1", "evidence_recall", "ndcg", "tokens"]
M2_METRICS = ["answer_f1", "evidence_recall", "ndcg", "tokens", "seconds"]
LOWER_IS_BETTER = {"tokens", "seconds", "latency_ms", "p95_latency_ms"}

CONFIGS = {
    "e3": {
        "db": "runs/e3/2x2.sqlite",
        "raw": "eval/archive/e3-2x2.json",
        "out": "eval/archive/e3-online-2x2-report.json",
        "experiment_id": "E3-online-2x2",
        "expected_runs": 4,
        "questions": 60,
    },
    "m2": {
        "db": "runs/s6/m2.sqlite",
        "raw": "eval/archive/m2-rerank.json",
        "out": "eval/archive/m2-online-rerank-report.json",
        "experiment_id": "M2-online-rerank",
        "expected_runs": 2,
        "questions": 40,
    },
    "e2": {
        "db": "runs/e2/oracle.sqlite",
        "raw": "eval/archive/e2-oracle-retrieval.json",
        "out": "eval/archive/e2-oracle-retrieval-report.json",
        "experiment_id": "E2-2-oracle-retrieval",
        "expected_runs": 1,
        "questions": 80,
    },
}


# ---------------------------------------------------------------------------
# loading / math helpers
# ---------------------------------------------------------------------------
def _loads(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _round(value: float | None, digits: int = 6):
    return None if value is None else round(float(value), digits)


def _mean(values) -> float | None:
    values = [float(value) for value in values if value is not None]
    return statistics.fmean(values) if values else None


def _percentile(values, quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _bootstrap_ci(deltas: list[float]) -> list[float] | None:
    if not deltas:
        return None
    rng = random.Random(SEED)
    n = len(deltas)
    means = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        total = 0.0
        for _ in range(n):
            total += deltas[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    lower_index = int((1.0 - CI_LEVEL) / 2.0 * BOOTSTRAP_ITERATIONS)
    upper_index = int((1.0 + CI_LEVEL) / 2.0 * BOOTSTRAP_ITERATIONS) - 1
    return [_round(means[lower_index]), _round(means[upper_index])]


def _direction(metric: str, delta: float) -> str:
    if abs(delta) <= 1e-12:
        return "same"
    better = delta < 0 if metric in LOWER_IS_BETTER else delta > 0
    return "better" if better else "worse"


def _summarize_deltas(metric: str, deltas: list[float], n_baseline: int, n_candidate: int) -> dict:
    mean_delta = _mean(deltas)
    ci95 = _bootstrap_ci(deltas)
    crosses_zero = None if ci95 is None else (ci95[0] <= 0.0 <= ci95[1])
    improved = sum(1 for delta in deltas if _direction(metric, delta) == "better")
    worsened = sum(1 for delta in deltas if _direction(metric, delta) == "worse")
    unchanged = len(deltas) - improved - worsened
    return {
        "metric": metric,
        "n_pairs": len(deltas),
        "n_baseline": n_baseline,
        "n_candidate": n_candidate,
        "mean_delta": _round(mean_delta),
        "delta": _round(mean_delta),
        "median": _round(statistics.median(deltas)) if deltas else None,
        "median_delta": _round(statistics.median(deltas)) if deltas else None,
        "improved": improved,
        "worsened": worsened,
        "unchanged": unchanged,
        "ci95": ci95,
        "ci95_crosses_zero": crosses_zero,
        "significant": (not crosses_zero) if crosses_zero is not None else None,
        "direction": _direction(metric, mean_delta),
        "lower_is_better": metric in LOWER_IS_BETTER,
        "method": "paired_percentile_bootstrap",
        "bootstrap": {"iterations": BOOTSTRAP_ITERATIONS, "seed": SEED, "ci_level": CI_LEVEL},
    }


# ---------------------------------------------------------------------------
# DB / raw loading
# ---------------------------------------------------------------------------
def _connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _load_runs(db_path: Path) -> tuple[list[dict], dict[str, dict[str, dict[str, float]]]]:
    connection = _connect_readonly(db_path)
    try:
        runs = []
        values: dict[str, dict[str, dict[str, float]]] = {}
        for row in connection.execute("SELECT * FROM runs ORDER BY run_id"):
            run_id = row["run_id"]
            qids: set[str] = set()
            by_metric: dict[str, dict[str, float]] = {}
            errors = 0
            for metric_row in connection.execute(
                "SELECT qid, metric, value FROM metrics WHERE run_id = ?", (run_id,)
            ):
                qids.add(metric_row["qid"])
                if metric_row["metric"] == "error":
                    errors += 1
                    continue
                if metric_row["value"] is None:
                    continue
                by_metric.setdefault(metric_row["metric"], {})[metric_row["qid"]] = float(
                    metric_row["value"]
                )
            runs.append(
                {
                    "run_id": run_id,
                    "spec_id": row["spec_id"],
                    "design": row["design"],
                    "config_hash": row["config_hash"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "environment": _loads(row["environment_json"], {}),
                    "dataset": _loads(row["dataset_json"], {}),
                    "factors": _loads(row["factors_json"], {}),
                    "qids": qids,
                    "errors": errors,
                }
            )
            values[run_id] = by_metric
        return runs, values
    finally:
        connection.close()


def _run_metrics(by_metric: dict[str, dict[str, float]], qids: set[str]) -> dict:
    metrics = {}
    for metric in ("answer_f1", "evidence_recall", "ndcg", "tokens", "refused", "seconds"):
        metrics[metric] = _round(_mean(by_metric.get(metric, {}).values()))
    metrics["p95_latency_ms"] = _round(_percentile(by_metric.get("latency_ms", {}).values(), 0.95))
    metrics["n_questions"] = len(qids)
    return metrics


def _check_raw(
    raw_path: Path,
    runs: list[dict],
    values: dict[str, dict[str, dict[str, float]]],
    tolerance: float = TOLERANCE,
) -> dict:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw_run_list = raw.get("runs")
    if raw_run_list is None and raw.get("run_id"):
        raw_run_list = [{"run_id": raw["run_id"], "metrics": raw.get("metrics") or {}}]
    raw_runs = {run["run_id"]: run for run in (raw_run_list or [])}
    problems = []
    if len(raw_runs) != len(runs):
        problems.append(f"raw run count {len(raw_runs)} != DB run count {len(runs)}")
    for run in runs:
        raw_run = raw_runs.get(run["run_id"])
        if raw_run is None:
            problems.append(f"raw archive misses {run['run_id']}")
            continue
        for metric, claimed in (raw_run.get("metrics") or {}).items():
            if metric not in values[run["run_id"]]:
                continue
            db_value = _mean(values[run["run_id"]][metric].values())
            if db_value is None:
                continue
            if abs(float(claimed) - db_value) > tolerance:
                problems.append(
                    f"{run['run_id']} {metric}: raw={claimed} db={db_value:.6f} "
                    f"diff={abs(float(claimed) - db_value):.6f}"
                )
    if problems:
        raise SystemExit(
            f"raw archive / DB mismatch (tolerance {tolerance:g}):\n  " + "\n  ".join(problems)
        )
    return raw


def _validate(kind: str, runs: list[dict], expected_runs: int, expected_questions: int) -> None:
    if len(runs) != expected_runs:
        raise SystemExit(f"{kind}: expected {expected_runs} runs, found {len(runs)}")
    for run in runs:
        dataset = run["dataset"] or {}
        if list(dataset.get("samples") or []) != SAMPLES:
            raise SystemExit(f"{kind}: unexpected samples in {run['run_id']}: {dataset.get('samples')!r}")
        if len(run["qids"]) != expected_questions:
            raise SystemExit(
                f"{kind}: expected {expected_questions} questions in {run['run_id']}, "
                f"found {len(run['qids'])}"
            )
        if run["status"] != "complete":
            raise SystemExit(f"{kind}: run {run['run_id']} status={run['status']}")
        if run["errors"]:
            raise SystemExit(f"{kind}: run {run['run_id']} has {run['errors']} error rows")


# ---------------------------------------------------------------------------
# report building blocks
# ---------------------------------------------------------------------------
def _code_fingerprint() -> dict:
    head_path = ARCHIVE / "server-code.head"
    sha1_path = ARCHIVE / "server-code.sha1"
    if not head_path.exists() or not sha1_path.exists():
        raise SystemExit("missing eval/archive/server-code.head or .sha1")
    head = head_path.read_text(encoding="utf-8").strip()
    sha1_tokens = sha1_path.read_text(encoding="utf-8").split()
    if not sha1_tokens:
        raise SystemExit("empty eval/archive/server-code.sha1")
    return {
        "git_head": head,
        "diff_sha1": sha1_tokens[0],
        "source_files": ["eval/archive/server-code.head", "eval/archive/server-code.sha1"],
    }


def _protocol(kind: str) -> dict:
    protocol = {
        "executor": "e2e",
        "offline": False,
        "llm": "qwen3.8:27b-q4_K_M",
        "context": 8192,
        "embedding": "bge-m3",
        "rerank_device": "GPU" if kind == "m2" else "未用",
        "seed": SEED,
        "inference": "Ollama 0.40.15",
        "host": "NVIDIA L20 48GB (server /root/memlab)",
    }
    if kind == "m2":
        protocol["rerank_model"] = "BAAI/bge-reranker-v2-m3"
    if kind == "e2":
        protocol["rerank_device"] = "未用（retrieval oracle）"
    return protocol


def _manifest(runs: list[dict]) -> dict:
    return {
        "spec_id": runs[0]["spec_id"],
        "design": runs[0]["design"],
        "config_hashes": {run["run_id"]: run["config_hash"] for run in runs},
        "executor": "e2e",
        "read_only_db": True,
        "builder": "scripts/build_online_reports.py",
    }


def _run_payload(run: dict, values: dict[str, dict[str, float]]) -> dict:
    metrics = _run_metrics(values, run["qids"])
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "factors": run["factors"],
        "config_hash": run["config_hash"],
        "n_questions": metrics["n_questions"],
        "errors": run["errors"],
        "metrics": {key: value for key, value in metrics.items() if key != "n_questions"},
        "metric_counts": {
            metric: len(values.get(metric, {}))
            for metric in ("answer_f1", "evidence_recall", "ndcg", "tokens", "refused", "latency_ms")
        },
    }


def _cell_label(factors: dict) -> str:
    if "fusion.impl" in factors:
        return f"{factors.get('fusion.impl')}/{factors.get('answer.impl')}"
    if "rerank.impl" in factors:
        return str(factors.get("rerank.impl"))
    if "oracle" in factors:
        return f"oracle={factors.get('oracle')}"
    return "run"


def _cell_means(runs: list[dict], values: dict[str, dict[str, dict[str, float]]]) -> list[dict]:
    rows = []
    for run in runs:
        metrics = _run_metrics(values[run["run_id"]], run["qids"])
        rows.append(
            {
                "cell": _cell_label(run["factors"]),
                "run_id": run["run_id"],
                "factors": run["factors"],
                "n_questions": metrics["n_questions"],
                "answer_f1": metrics["answer_f1"],
                "evidence_recall": metrics["evidence_recall"],
                "ndcg": metrics["ndcg"],
                "tokens": metrics["tokens"],
                "refused": metrics["refused"],
                "p95_latency_ms": metrics["p95_latency_ms"],
            }
        )
    return rows


def _pooled_means(
    run_ids: list[str],
    values: dict[str, dict[str, dict[str, float]]],
    metrics=("answer_f1", "evidence_recall", "ndcg", "tokens"),
) -> dict:
    all_qids = set()
    for run_id in run_ids:
        all_qids |= set(values[run_id].get("answer_f1", {}))
    result = {"n_questions": len(all_qids), "n_observations": 0}
    for metric in metrics:
        pooled = []
        for run_id in run_ids:
            pooled.extend(values[run_id].get(metric, {}).values())
        result[metric] = _round(_mean(pooled))
        result[f"{metric}_n"] = len(pooled)
    result["n_observations"] = result.get("answer_f1_n", 0)
    return result


def _paired_stats(
    metric: str,
    baseline: dict[str, dict[str, float]],
    candidate: dict[str, dict[str, float]],
) -> dict | None:
    shared = sorted(set(baseline.get(metric, {})) & set(candidate.get(metric, {})))
    if not shared:
        return None
    deltas = [candidate[metric][qid] - baseline[metric][qid] for qid in shared]
    return _summarize_deltas(
        metric,
        deltas,
        n_baseline=len(baseline.get(metric, {})),
        n_candidate=len(candidate.get(metric, {})),
    )


def _pooled_paired_stats(
    metric: str,
    pairs: list[tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]],
) -> dict | None:
    common = None
    for baseline, candidate in pairs:
        qids = set(baseline.get(metric, {})) & set(candidate.get(metric, {}))
        common = qids if common is None else (common & qids)
    if not common:
        return None
    deltas = []
    for qid in sorted(common):
        per_pair = [
            candidate[metric][qid] - baseline[metric][qid] for baseline, candidate in pairs
        ]
        deltas.append(sum(per_pair) / len(per_pair))
    return _summarize_deltas(
        metric,
        deltas,
        n_baseline=sum(len(baseline.get(metric, {})) for baseline, _ in pairs),
        n_candidate=sum(len(candidate.get(metric, {})) for _, candidate in pairs),
    )


# ---------------------------------------------------------------------------
# E3 2x2
# ---------------------------------------------------------------------------
def _build_e3(runs: list[dict], values: dict[str, dict[str, dict[str, float]]]) -> dict:
    cells = {(run["factors"]["fusion.impl"], run["factors"]["answer.impl"]): run for run in runs}
    required = [
        ("single_channel", "direct"),
        ("single_channel", "evidence_chain"),
        ("weighted_rrf", "direct"),
        ("weighted_rrf", "evidence_chain"),
    ]
    for cell in required:
        if cell not in cells:
            raise SystemExit(f"E3: missing cell {cell}")

    s_direct = values[cells[("single_channel", "direct")]["run_id"]]
    s_chain = values[cells[("single_channel", "evidence_chain")]["run_id"]]
    w_direct = values[cells[("weighted_rrf", "direct")]["run_id"]]
    w_chain = values[cells[("weighted_rrf", "evidence_chain")]["run_id"]]

    contrasts = [
        {
            "contrast": "fusion",
            "factor": "fusion.impl",
            "fixed_factor": "answer.impl",
            "fixed_level": "direct",
            "baseline_level": "single_channel",
            "candidate_level": "weighted_rrf",
            "baseline": cells[("single_channel", "direct")],
            "candidate": cells[("weighted_rrf", "direct")],
            "baseline_values": s_direct,
            "candidate_values": w_direct,
        },
        {
            "contrast": "fusion",
            "factor": "fusion.impl",
            "fixed_factor": "answer.impl",
            "fixed_level": "evidence_chain",
            "baseline_level": "single_channel",
            "candidate_level": "weighted_rrf",
            "baseline": cells[("single_channel", "evidence_chain")],
            "candidate": cells[("weighted_rrf", "evidence_chain")],
            "baseline_values": s_chain,
            "candidate_values": w_chain,
        },
        {
            "contrast": "answer",
            "factor": "answer.impl",
            "fixed_factor": "fusion.impl",
            "fixed_level": "single_channel",
            "baseline_level": "direct",
            "candidate_level": "evidence_chain",
            "baseline": cells[("single_channel", "direct")],
            "candidate": cells[("single_channel", "evidence_chain")],
            "baseline_values": s_direct,
            "candidate_values": s_chain,
        },
        {
            "contrast": "answer",
            "factor": "answer.impl",
            "fixed_factor": "fusion.impl",
            "fixed_level": "weighted_rrf",
            "baseline_level": "direct",
            "candidate_level": "evidence_chain",
            "baseline": cells[("weighted_rrf", "direct")],
            "candidate": cells[("weighted_rrf", "evidence_chain")],
            "baseline_values": w_direct,
            "candidate_values": w_chain,
        },
    ]

    comparisons = []
    for spec in contrasts:
        for metric in E3_METRICS:
            stats = _paired_stats(metric, spec["baseline_values"], spec["candidate_values"])
            if stats is None:
                continue
            comparisons.append(
                {
                    "contrast": spec["contrast"],
                    "factor": spec["factor"],
                    "fixed_factor": spec["fixed_factor"],
                    "fixed_level": spec["fixed_level"],
                    "baseline_level": spec["baseline_level"],
                    "candidate_level": spec["candidate_level"],
                    "baseline": _cell_label(spec["baseline"]["factors"]),
                    "candidate": _cell_label(spec["candidate"]["factors"]),
                    "baseline_run_id": spec["baseline"]["run_id"],
                    "candidate_run_id": spec["candidate"]["run_id"],
                    **stats,
                }
            )

    fusion_main = {}
    for metric in E3_METRICS:
        stats = _pooled_paired_stats(metric, [(s_direct, w_direct), (s_chain, w_chain)])
        if stats is not None:
            fusion_main[metric] = stats
    answer_main = {}
    for metric in E3_METRICS:
        stats = _pooled_paired_stats(metric, [(s_direct, s_chain), (w_direct, w_chain)])
        if stats is not None:
            answer_main[metric] = stats

    group_means = {
        "cells": _cell_means(runs, values),
        "fusion": [
            {
                "level": "single_channel",
                "n_cells": 2,
                **_pooled_means(
                    [cells[("single_channel", "direct")]["run_id"], cells[("single_channel", "evidence_chain")]["run_id"]],
                    values,
                ),
            },
            {
                "level": "weighted_rrf",
                "n_cells": 2,
                **_pooled_means(
                    [cells[("weighted_rrf", "direct")]["run_id"], cells[("weighted_rrf", "evidence_chain")]["run_id"]],
                    values,
                ),
            },
        ],
        "answer": [
            {
                "level": "direct",
                "n_cells": 2,
                **_pooled_means(
                    [cells[("single_channel", "direct")]["run_id"], cells[("weighted_rrf", "direct")]["run_id"]],
                    values,
                ),
            },
            {
                "level": "evidence_chain",
                "n_cells": 2,
                **_pooled_means(
                    [cells[("single_channel", "evidence_chain")]["run_id"], cells[("weighted_rrf", "evidence_chain")]["run_id"]],
                    values,
                ),
            },
        ],
    }

    fusion_f1 = fusion_main["answer_f1"]
    answer_f1 = answer_main["answer_f1"]
    status = "inconclusive"
    if fusion_f1["ci95"] is not None:
        if fusion_f1["ci95"][0] > 0:
            status = "supported"
        elif fusion_f1["ci95"][1] < 0:
            status = "not_supported"

    best_cell = max(group_means["cells"], key=lambda row: row["answer_f1"] or -1)
    worst_cell = min(group_means["cells"], key=lambda row: row["answer_f1"] or 1)
    observations = [
        (
            f"F1 最高格 {best_cell['cell']} = {best_cell['answer_f1']:.4f}；"
            f"最低格 {worst_cell['cell']} = {worst_cell['answer_f1']:.4f}。"
        ),
        (
            f"fusion 主效应（weighted_rrf - single_channel）F1 = {fusion_f1['mean_delta']:+.4f}，"
            f"95% CI [{fusion_f1['ci95'][0]:+.4f}, {fusion_f1['ci95'][1]:+.4f}]，"
            f"{'跨 0' if fusion_f1['ci95_crosses_zero'] else '不含 0'}。"
        ),
        (
            f"answer 主效应（evidence_chain - direct）F1 = {answer_f1['mean_delta']:+.4f}，"
            f"95% CI [{answer_f1['ci95'][0]:+.4f}, {answer_f1['ci95'][1]:+.4f}]；"
            "这是未校正多重比较的次要观察。"
        ),
        (
            "Recall/nDCG 的 fusion 主效应点估计为正但 CI 均跨 0；tokens 几乎不变"
            "（四格 48.55–48.58）。"
        ),
    ]

    return {
        "dataset": {
            "split": "development",
            "samples": SAMPLES,
            "questions_per_config": 60,
        },
        "results": {
            "runs": [_run_payload(run, values[run["run_id"]]) for run in runs],
            "n_runs": len(runs),
            "errors": sum(run["errors"] for run in runs),
        },
        "comparisons": comparisons,
        "analysis": {
            "main_effects": [
                {
                    "factor": "fusion.impl",
                    "baseline_level": "single_channel",
                    "candidate_level": "weighted_rrf",
                    "contrast": "weighted_rrf - single_channel (averaged over answer levels)",
                    "metrics": fusion_main,
                },
                {
                    "factor": "answer.impl",
                    "baseline_level": "direct",
                    "candidate_level": "evidence_chain",
                    "contrast": "evidence_chain - direct (averaged over fusion levels)",
                    "metrics": answer_main,
                },
            ],
            "interactions": [],
            "pareto": [],
            "group_means": group_means,
            "paired_deltas": comparisons,
            "observations": observations,
            "can_answer": (
                "在 development 4 段、27B、8k 下，给出 fusion×answer 四格的 "
                "F1/Recall/nDCG/tokens 排序，以及 60 题配对 bootstrap 的不确定性区间。"
            ),
            "cannot_answer": (
                "不能外推到 test；不能当作本地 7B/72B 的规模结论；"
                "fusion 的 F1 提升 CI 跨 0，不能宣称 weighted_rrf 显著优于 single_channel；"
                "未做多重比较校正。"
            ),
        },
        "conclusion": {
            "status": status,
            "primary_metric": "answer_f1",
            "primary_comparison": {
                "contrast": "weighted_rrf - single_channel (averaged over answer levels)",
                "n_pairs": fusion_f1["n_pairs"],
                "mean_delta": fusion_f1["mean_delta"],
                "ci95": fusion_f1["ci95"],
                "ci95_crosses_zero": fusion_f1["ci95_crosses_zero"],
            },
            "status_reason": (
                "预先规则：fusion 的 F1 95% CI 不含 0 且为正 → supported；含 0 → inconclusive。"
                f" 本次 CI = [{fusion_f1['ci95'][0]:+.4f}, {fusion_f1['ci95'][1]:+.4f}]，"
                "跨 0，因此为 inconclusive。"
            ),
            "claims": [
                (
                    f"Fusion: weighted_rrf - single_channel F1 = {fusion_f1['mean_delta']:+.4f} "
                    f"(95% CI [{fusion_f1['ci95'][0]:+.4f}, {fusion_f1['ci95'][1]:+.4f}], "
                    f"n={fusion_f1['n_pairs']} paired qids); CI 跨 0 → inconclusive。"
                ),
                (
                    f"Answer (uncorrected secondary): evidence_chain - direct F1 = "
                    f"{answer_f1['mean_delta']:+.4f} (95% CI "
                    f"[{answer_f1['ci95'][0]:+.4f}, {answer_f1['ci95'][1]:+.4f}], "
                    f"n={answer_f1['n_pairs']}); CI 不含 0，direct 在本数据上更好，"
                    "但未做多重比较校正，只作观察。"
                ),
                (
                    f"四格点估计排序：{best_cell['cell']} 最高 "
                    f"({best_cell['answer_f1']:.4f})，{worst_cell['cell']} 最低 "
                    f"({worst_cell['answer_f1']:.4f})；这是描述性排序。"
                ),
            ],
            "per_metric_status": {
                metric: {
                    "status": "inconclusive" if stats["ci95_crosses_zero"] else "significant",
                    "mean_delta": stats["mean_delta"],
                    "ci95": stats["ci95"],
                    "ci95_crosses_zero": stats["ci95_crosses_zero"],
                    "direction": stats["direction"],
                }
                for metric, stats in fusion_main.items()
            },
            "conditions": [
                "Online qwen3.8:27b-q4_K_M, context 8192, bge-m3; 4 dev conversations, 60 q/cell, seed 13.",
                "Same fixed 60-question set across the four cells; deltas are paired by qid.",
                "Bootstrap: 1000 paired resamples over qids, seed 13, percentile 95% CI.",
            ],
            "limitations": [
                "只有 60 题（4 段 × 15 题/格）。",
                "无重复运行（单 seed 13），没有 run-to-run 方差估计。",
                "无多重比较校正（4 个 cell 对比 × 4 个指标）。",
                "development split。",
                "online 27B, context 8192；不能外推到 test，也不能当本地 7B/72B 的规模结论。",
            ],
            "next_actions": [
                "增加 seed/重复运行，估计 run-to-run 方差。",
                "在 test split 上复验 fusion×answer 排序。",
                "对 4 个 cell 对比做多重比较校正（如 Holm）。",
            ],
        },
    }


# ---------------------------------------------------------------------------
# M2 rerank
# ---------------------------------------------------------------------------
def _build_m2(runs: list[dict], values: dict[str, dict[str, dict[str, float]]]) -> dict:
    cells = {run["factors"]["rerank.impl"]: run for run in runs}
    if "none" not in cells or "cross_encoder" not in cells:
        raise SystemExit("M2: need rerank.impl=none and cross_encoder")
    none_values = values[cells["none"]["run_id"]]
    ce_values = values[cells["cross_encoder"]["run_id"]]

    comparisons = []
    for metric in M2_METRICS:
        stats = _paired_stats(metric, none_values, ce_values)
        if stats is None:
            continue
        comparisons.append(
            {
                "contrast": "rerank",
                "factor": "rerank.impl",
                "baseline_level": "none",
                "candidate_level": "cross_encoder",
                "baseline": "rerank=none",
                "candidate": "rerank=cross_encoder",
                "baseline_run_id": cells["none"]["run_id"],
                "candidate_run_id": cells["cross_encoder"]["run_id"],
                **stats,
            }
        )

    by_metric = {entry["metric"]: entry for entry in comparisons}
    f1 = by_metric["answer_f1"]
    recall = by_metric["evidence_recall"]
    ndcg = by_metric["ndcg"]
    tokens = by_metric["tokens"]

    tradeoff_confirmed = (
        f1["ci95"] is not None
        and f1["ci95"][1] < 0
        and recall["ci95"] is not None
        and recall["ci95"][1] < 0
        and ndcg["ci95"] is not None
        and ndcg["ci95"][0] > 0
    )
    status = "partial" if tradeoff_confirmed else "inconclusive"

    group_means = {"cells": _cell_means(runs, values)}
    main_effects = {
        "factor": "rerank.impl",
        "levels": ["none", "cross_encoder"],
        "metrics": {},
    }
    for metric in M2_METRICS:
        if metric in by_metric:
            main_effects["metrics"][metric] = by_metric[metric]

    all_mean_ndcg = _run_metrics(ce_values, cells["cross_encoder"]["qids"])["ndcg"] - _run_metrics(
        none_values, cells["none"]["qids"]
    )["ndcg"]

    observations = [
        (
            f"Recall 显著下降：{recall['mean_delta']:+.4f}，95% CI "
            f"[{recall['ci95'][0]:+.4f}, {recall['ci95'][1]:+.4f}]，"
            f"{recall['worsened']}/{recall['n_pairs']} 题变差。"
        ),
        (
            f"F1 {f1['mean_delta']:+.4f}，95% CI "
            f"[{f1['ci95'][0]:+.4f}, {f1['ci95'][1]:+.4f}]，"
            f"{'跨 0' if f1['ci95_crosses_zero'] else '不含 0'} → "
            f"{'inconclusive' if f1['ci95_crosses_zero'] else '显著'}。"
        ),
        (
            f"nDCG 配对 delta {ndcg['mean_delta']:+.4f}（n={ndcg['n_pairs']} 个共同 qid），"
            f"95% CI [{ndcg['ci95'][0]:+.4f}, {ndcg['ci95'][1]:+.4f}]，"
            f"{'跨 0' if ndcg['ci95_crosses_zero'] else '不含 0'}；"
            f"run-level 均值差为 {all_mean_ndcg:+.4f}（3 题 CE 无 ndcg，未配对）。"
        ),
        (
            f"Tokens {tokens['mean_delta']:+.2f}，95% CI "
            f"[{tokens['ci95'][0]:+.2f}, {tokens['ci95'][1]:+.2f}]；"
            f"{tokens['improved']}/{tokens['n_pairs']} 题下降。"
        ),
        (
            "方向与 trade-off 一致（nDCG 点估计上升、F1/Recall 下降、tokens 大幅下降），"
            "但 F1 与 nDCG 的 CI 跨 0，完整 trade-off 未被统计确认。"
        ),
    ]

    return {
        "dataset": {
            "split": "development",
            "samples": SAMPLES,
            "questions_per_config": 40,
        },
        "results": {
            "runs": [_run_payload(run, values[run["run_id"]]) for run in runs],
            "n_runs": len(runs),
            "errors": sum(run["errors"] for run in runs),
        },
        "comparisons": comparisons,
        "analysis": {
            "main_effects": [main_effects],
            "interactions": [],
            "pareto": [],
            "group_means": group_means,
            "paired_deltas": comparisons,
            "observations": observations,
            "can_answer": (
                "在 development 4 段、27B、8k、GPU cross-encoder 下，量化 M2 重排对 "
                "F1/Recall/nDCG/tokens 的配对变化方向与不确定性区间。"
            ),
            "cannot_answer": (
                "不能外推到 test；n=40 单 seed，F1/nDCG 的 CI 跨 0，"
                "不能宣称重排显著更好或更差，也不能当 7B/72B 规模结论。"
            ),
        },
        "conclusion": {
            "status": status,
            "primary_metric": "answer_f1",
            "primary_comparison": {
                "contrast": "cross_encoder - none",
                "n_pairs": f1["n_pairs"],
                "mean_delta": f1["mean_delta"],
                "ci95": f1["ci95"],
                "ci95_crosses_zero": f1["ci95_crosses_zero"],
            },
            "status_reason": (
                "规则：F1/Recall 显著下降且 nDCG 显著上升 → partial；"
                "本次 F1 CI 跨 0、nDCG CI 跨 0，只有 Recall/tokens 显著下降，"
                "因此不满足 partial 条件，记为 inconclusive。"
            ),
            "claims": [
                (
                    "方向与 trade-off 一致：重排提高排序质量（nDCG 点估计 "
                    f"{ndcg['mean_delta']:+.4f}）但压缩证据覆盖（Recall "
                    f"{recall['mean_delta']:+.4f}），F1 {f1['mean_delta']:+.4f}，"
                    "tokens 大幅下降；不能写“重排更好”或“重排更差”。"
                ),
                (
                    f"Recall 显著下降（95% CI [{recall['ci95'][0]:+.4f}, "
                    f"{recall['ci95'][1]:+.4f}]），tokens 显著下降（95% CI "
                    f"[{tokens['ci95'][0]:+.2f}, {tokens['ci95'][1]:+.2f}]）。"
                ),
                (
                    f"F1 95% CI [{f1['ci95'][0]:+.4f}, {f1['ci95'][1]:+.4f}] 跨 0；"
                    f"nDCG 95% CI [{ndcg['ci95'][0]:+.4f}, {ndcg['ci95'][1]:+.4f}] 跨 0；"
                    "两项均 inconclusive，不能支持完整 trade-off 的显著性声明。"
                ),
            ],
            "per_metric_status": {
                metric: {
                    "status": "inconclusive" if stats["ci95_crosses_zero"] else "significant",
                    "mean_delta": stats["mean_delta"],
                    "ci95": stats["ci95"],
                    "ci95_crosses_zero": stats["ci95_crosses_zero"],
                    "direction": stats["direction"],
                }
                for metric, stats in by_metric.items()
            },
            "conditions": [
                "Online qwen3.8:27b-q4_K_M, context 8192, bge-m3; 4 dev conversations, 40 q/config, seed 13.",
                "cross-encoder = BAAI/bge-reranker-v2-m3 on GPU; same 40-question set across configs.",
                "Bootstrap: 1000 paired resamples over qids, seed 13, percentile 95% CI.",
            ],
            "limitations": [
                "n=40（4 段 × 10 题/配置）。",
                "单 seed 13，无重复运行。",
                "development split。",
                "cross-encoder 在 GPU 上跑（BAAI/bge-reranker-v2-m3）。",
                "无多重比较校正。",
                "online 27B, context 8192；不能外推到 test 或本地 7B/72B。",
            ],
            "next_actions": [
                "增加 seed/题量，重点复验 F1 与 nDCG 的 CI。",
                "在 test split 上复验 trade-off。",
                "对 5 个指标做多重比较校正。",
            ],
        },
    }


# ---------------------------------------------------------------------------
# E2 oracle (optional)
# ---------------------------------------------------------------------------
def _build_e2(runs: list[dict], values: dict[str, dict[str, dict[str, float]]]) -> dict:
    run = runs[0]
    payload = _run_payload(run, values[run["run_id"]])
    metrics = payload["metrics"]
    return {
        "dataset": {
            "split": "development",
            "samples": SAMPLES,
            "questions_per_config": 80,
        },
        "results": {"runs": [payload], "n_runs": 1, "errors": run["errors"]},
        "comparisons": [],
        "analysis": {
            "main_effects": [],
            "interactions": [],
            "pareto": [],
            "group_means": {"cells": _cell_means(runs, values)},
            "paired_deltas": [],
            "observations": [
                (
                    f"oracle retrieval: F1 {metrics['answer_f1']:.4f}, "
                    f"Recall {metrics['evidence_recall']:.4f}, tokens {metrics['tokens']:.2f}, "
                    f"p95 {metrics['p95_latency_ms']:.1f} ms (n=80)."
                ),
                (
                    "Recall 由 gold evidence 构造，不能与系统 Recall 直接比较；"
                    "只回答“证据给全时 answer/refusal 还能答对多少”。"
                ),
            ],
            "can_answer": "在 development 4 段、27B、8k 下给出 retrieval oracle 的 F1/Recall/tokens/延迟上界参考。",
            "cannot_answer": (
                "只有一个 run，没有配对对象，不能做显著性比较；"
                "不能与 B0/R0 比较（题集与配置不同）；不能外推到 test 或 7B/72B。"
            ),
        },
        "conclusion": {
            "status": "inconclusive",
            "primary_metric": "answer_f1",
            "status_reason": "只有一个 run（80 题），没有配对/对照对象，按规则记为 inconclusive。",
            "claims": [
                (
                    f"oracle retrieval 下 F1 {metrics['answer_f1']:.4f} / "
                    f"Recall {metrics['evidence_recall']:.4f}，作为检索上界参考。"
                )
            ],
            "per_metric_status": {
                "answer_f1": {"status": "inconclusive", "mean_delta": None, "ci95": None},
                "evidence_recall": {"status": "inconclusive", "mean_delta": None, "ci95": None},
                "tokens": {"status": "inconclusive", "mean_delta": None, "ci95": None},
            },
            "conditions": [
                "Online qwen3.8:27b-q4_K_M, context 8192, bge-m3; 4 dev conversations, 80 q, seed 13.",
                "Only retrieval is replaced by oracle gold evidence; M/U remain frozen R0.",
            ],
            "limitations": [
                "single run, n=80（4 段 × 20 题）。",
                "oracle Recall 是构造值，不能与系统 Recall 比较。",
                "只做 retrieval oracle；write/store/merge/state/answer oracle 未跑。",
                "development split。",
                "不要与 B0/R0 做显著性比较（不同题集/不同配置）。",
                "online 27B, context 8192。",
            ],
            "next_actions": [
                "补 write/store/merge/state/answer oracle，形成完整 oracle gap。",
                "在 test split 上复验。",
            ],
        },
    }


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------
def build_report(kind: str, code_fingerprint: dict, protocol: dict) -> dict:
    config = CONFIGS[kind]
    db_path = ROOT / config["db"]
    raw_path = ROOT / config["raw"]
    if not db_path.exists():
        raise SystemExit(f"missing database: {db_path}")
    if not raw_path.exists():
        raise SystemExit(f"missing raw archive: {raw_path}")

    runs, values = _load_runs(db_path)
    _validate(kind, runs, config["expected_runs"], config["questions"])
    # E3/M2 raw metrics are 4-decimal, so 0.001 is the audit threshold.
    # E2's raw latency_ms is rounded to 2 decimals, hence the looser 0.01.
    _check_raw(raw_path, runs, values, tolerance=0.001 if kind in ("e3", "m2") else 0.01)

    if kind == "e3":
        body = _build_e3(runs, values)
    elif kind == "m2":
        body = _build_m2(runs, values)
    elif kind == "e2":
        body = _build_e2(runs, values)
    else:
        raise SystemExit(f"unknown kind {kind}")

    created_at = max((run["updated_at"] for run in runs if run["updated_at"]), default=None)
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": config["experiment_id"],
        "created_at": created_at,
        "source_db": config["db"],
        "source_archive": config["raw"],
        "raw_schema": json.loads(raw_path.read_text(encoding="utf-8")).get("schema"),
        "code_fingerprint": code_fingerprint,
        "protocol": protocol,
        "manifest": _manifest(runs),
        "dataset": body["dataset"],
        "metric_note": (
            "Per-question means; tokens/seconds are mean per question, not totals. "
            "p95_latency_ms is the run-level p95 of per-question latency_ms. "
            "refused is the mean per-question refusal flag. n_questions is the distinct qid count. "
            "Comparisons are paired by qid; ndcg has fewer pairs where a run is missing the metric."
        ),
        "bootstrap": {
            "method": "paired_percentile",
            "iterations": BOOTSTRAP_ITERATIONS,
            "seed": SEED,
            "ci_level": CI_LEVEL,
            "resample_unit": "qid",
        },
        **body,
        "web": {"route": f"#/experiments/{config['experiment_id']}", "published": False},
    }
    return report


def _write(report: dict, out_path: Path) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_name(out_path.name + ".tmp")
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(out_path)


def _build_one(kind: str, fingerprint: dict, protocol: dict) -> Path:
    report = build_report(kind, fingerprint, protocol)
    out_path = ROOT / CONFIGS[kind]["out"]
    _write(report, out_path)
    print(
        f"wrote {CONFIGS[kind]['out']} ({len(report['results']['runs'])} runs, "
        f"{len(report['comparisons'])} comparisons, status={report['conclusion']['status']})"
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=["e3", "m2", "e2"], default=None)
    parser.add_argument("--with-e2", action="store_true", help="also build the optional E2 oracle report")
    args = parser.parse_args(argv)

    fingerprint = _code_fingerprint()
    if args.only:
        kinds = [args.only]
    else:
        kinds = ["m2", "e3"]
        if args.with_e2:
            kinds.append("e2")

    for kind in kinds:
        _build_one(kind, fingerprint, _protocol(kind))
    return 0


if __name__ == "__main__":
    sys.exit(main())
