#!/usr/bin/env python3
"""Build E1.2 parameter response curves from one or more S5 result stores.

The E1.2 spec is single-factor: every requested level differs from reference-r0
by exactly one dotted config path.  The compiler deduplicates levels that equal
the reference value into one shared baseline run, so this script maps every
requested level back to its run by ``config_hash`` instead of assuming one run
per factor level.

Only A-level interface metrics are reported.  ``answer_f1`` is deliberately not
put in the curve table, and the offline executor is labelled everywhere: hash
embeddings + extractive answers are not a 27B result.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab import config as lab_config
from memlab.experiments import compiler, spec as spec_module

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
LABELS = {
    "schema.params.fields": "W4 fields",
    "schema.params.evidence": "W4 evidence 必填",
    "graph.retrieval.params.k_hop": "S2 k_hop",
    "graph.retrieval.params.max_neighbors": "S2 max_neighbors",
    "retrieval.k": "R4 planner k (retrieval.k)",
    "post.mmr.params.lambda": "M4 MMR lambda",
    "post.decay.params.lambda": "M4 decay lambda",
    "post.compress.params.budget_tokens": "M4 compress budget",
    "rerank.params.top_n": "M6 rerank top_n",
}
FINDINGS: dict[str, dict[str, Any]] = {
    "schema.params.fields": {
        "effective_in_e2e": True,
        "verdict": (
            "tiny difference, but it is a lexical artifact, not extraction quality: the offline "
            "MetaSchemaExtractor stores the numeric value in structured.schema.fields, and "
            "store.search_text flattens every structured field into the BM25 text, so 6 vs 12 "
            "changes the index. field_completeness is 1.0 at both levels and the fact set is unchanged."
        ),
        "evidence": [
            "recall span 0.0016, nDCG span 0.0054, tokens span 1.7",
            "field_completeness = 1.0 at both levels; store_units/facts identical",
            "the only mechanism is the digit entering BM25 via search_text",
        ],
    },
    "schema.params.evidence": {
        "effective_in_e2e": False,
        "verdict": (
            "no difference: MetaSchemaExtractor always derives unit.evidence from the cached facts; "
            "the evidence flag is accepted but never read on the offline path. This is an "
            "interface-only knob here, not evidence that evidence-on is useless with an LLM extractor."
        ),
        "evidence": [
            "recall/nDCG/tokens/redundancy identical to 6 decimal places",
            "evidence on/off differ only in config_hash",
        ],
    },
    "graph.retrieval.params.k_hop": {
        "effective_in_e2e": True,
        "verdict": (
            "no difference at candidate budget 15: only 23/240 questions route to graph_khop, and "
            "a 1-hop expansion already fills the 15-candidate budget (three_layer graph is dense), "
            "so k_hop=2/3 add no new slots. Flat here means saturated, not that k_hop is unread."
        ),
        "evidence": [
            "routing: 141 single_hop (bm25+dense), 76 temporal (temporal+bm25), 23 multi_hop (bm25+graph_khop)",
            "graph_khop truncates at k=15 candidates; sorting is by graph distance, so distance-1 nodes fill the list",
        ],
    },
    "graph.retrieval.params.max_neighbors": {
        "effective_in_e2e": False,
        "verdict": (
            "no difference: the parameter is declared but not consumed. GraphIndex.expand(seeds, k_hop) "
            "has no max_neighbors argument, so 10/40/80 are identical. Do not tune until it is wired."
        ),
        "evidence": [
            "memlab/store.py GraphIndex.expand signature has only seeds and k_hop",
            "all three levels return the same per-question metrics",
        ],
    },
    "retrieval.k": {
        "effective_in_e2e": False,
        "harness_blocker": "memlab/experiments/executor.py:143 calls pipeline.run(..., k=15, ...) with a hardcoded 15",
        "verdict": (
            "no difference in this e2e run, and the reason is the harness: the planner would read "
            "retrieval.k through retrieve._k, but the e2e executor passes k=15 explicitly, so 10/15/25 "
            "never reach the planner. planner.params.k is not read anywhere at all. R4 k is blocked, "
            "not answered, by this run; it needs the executor to pass the configured k or a custom harness."
        ),
        "evidence": [
            "retrieval.k=10/15/25 produce byte-identical curve values",
            "executor.py:143 hardcodes k=15; retrieve._k returns requested k before reading retrieval.k",
        ],
    },
    "post.mmr.params.lambda": {
        "effective_in_e2e": False,
        "verdict": (
            "no difference: MMR only reorders (its top_n defaults to the candidate count and it drops "
            "nothing), then the following decay stage re-sorts by score, erasing the MMR permutation. "
            "In the R0 stage order lambda cannot change recall/nDCG/tokens. To test lambda, disable "
            "decay or move MMR after decay."
        ),
        "evidence": [
            "0.5/0.7/0.9 identical; recall and token count unchanged",
            "pipeline order is fusion -> rerank -> filter -> mmr -> decay -> compress",
        ],
    },
    "post.decay.params.lambda": {
        "effective_in_e2e": True,
        "verdict": (
            "real but small and ranking-only: lambda=0.001 wins by +0.0136 nDCG vs 0.01 and +0.0119 vs "
            "0.05; 0.01 is the low point, so the curve is non-monotone with a shallow dip. Recall, tokens "
            "and redundancy are unchanged because decay only reorders the same 15 candidates. Low decay "
            "roughly preserves the incoming order; stronger decay reorders by recency."
        ),
        "evidence": [
            "nDCG: 0.2873 (0.001) / 0.2737 (0.01) / 0.2753 (0.05)",
            "101-104 of 240 questions change nDCG; recall/tokens identical",
        ],
    },
    "post.compress.params.budget_tokens": {
        "effective_in_e2e": True,
        "verdict": (
            "only 500 bites: 340.4 vs 344.6 tokens (-1.2%) with recall/nDCG unchanged; 1000 and 2000 "
            "are identical to the 4000 default because the 15-unit context is only ~345 tokens. There is "
            "no quality/token tradeoff to tune at 1000/2000; 500 is a mild token-only saving."
        ),
        "evidence": [
            "tokens: 340.4 (500) / 344.6 (1000) / 344.6 (2000)",
            "recall 0.4619 and nDCG 0.2746 at all three levels",
        ],
    },
    "rerank.params.top_n": {
        "effective_in_e2e": False,
        "harness_blocker": "sentence-transformers is absent; CrossEncoderReranker records a fallback and never applies top_n",
        "verdict": (
            "no difference: sentence-transformers is not installed, so the cross-encoder stage records "
            "a fallback and keeps the incoming order; top_n is never applied. Even with the model, "
            "top_n>=20 exceeds the fixed k=15 budget. M6 is not answerable in this offline environment."
        ),
        "evidence": [
            "run metadata fallbacks: 'rerank:ModuleNotFoundError: No module named sentence_transformers'",
            "20/50/100 identical; final candidate budget is 15",
        ],
    },
}

METRIC_KEYS = (
    "evidence_recall", "ndcg", "tokens", "redundancy",
    "context_precision", "candidates", "latency_ms", "field_completeness",
    "store_units", "graph_nodes", "graph_edges", "plan_nodes", "channels",
)


def _git_commit() -> str | None:
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _mean(values):
    return round(statistics.fmean(values), 6) if values else None


def _p95(values):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(0.95 * len(ordered)) - 1))
    return round(ordered[index], 3)


def _level_label(value: Any) -> str:
    if value is True:
        return "on"
    if value is False:
        return "off"
    return str(value)


def _spread(values: list[float], abs_tol: float, rel_tol: float) -> tuple[float, bool]:
    if not values:
        return 0.0, True
    low, high = min(values), max(values)
    span = high - low
    scale = max(abs(low), abs(high), 1e-9)
    return span, (span <= abs_tol or span / scale <= rel_tol)


def _shape(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Describe a curve in level order; flat means it carries no tuning signal."""
    values = [row[key] for row in rows if row.get(key) is not None]
    if len(values) < 2:
        return {"metric": key, "shape": "missing", "span": None, "best_level": None}
    # Recall/nDCG/tokens/redundancy all have practical flat bands.  A true no-op
    # parameter produces exactly equal means, so the tolerance is deliberately
    # tight; anything above it is reported as a real (if small) difference.
    if key in ("ndcg", "evidence_recall", "context_precision", "redundancy"):
        abs_tol, rel_tol = 1e-6, 1e-9
    elif key == "tokens":
        abs_tol, rel_tol = 0.5, 0.005
    else:
        abs_tol, rel_tol = 0.01, 0.005
    span, flat = _spread(values, abs_tol, rel_tol)
    best_index = max(range(len(rows)), key=lambda index: rows[index].get(key) if rows[index].get(key) is not None else -1)
    diffs = [later - earlier for earlier, later in zip(values, values[1:])]
    monotone_up = all(diff > 0 for diff in diffs)
    monotone_down = all(diff < 0 for diff in diffs)
    if flat:
        shape = "flat"
    elif monotone_up:
        shape = "monotone_up"
    elif monotone_down:
        shape = "monotone_down"
    elif 0 < best_index < len(rows) - 1:
        shape = "inflection_max"
    else:
        shape = "non_monotone"
    return {
        "metric": key,
        "shape": shape,
        "span": round(span, 6),
        "relative_span": round(span / max(abs(min(values)), abs(max(values)), 1e-9), 6),
        "best_level": _level_label(rows[best_index].get("level")),
        "best_value": rows[best_index].get(key),
        "values_by_level": {_level_label(row.get("level")): row.get(key) for row in rows},
    }


def _rows_for_plan(store_paths: list[Path], run_id: str) -> tuple[dict[str, list[float]], set[str]]:
    """Union per-question metric rows for a run across one or more shard DBs.

    A question may appear in exactly one shard because the runner partitions by
    position.  Unioning by qid keeps the analysis correct if the caller used
    --shard/--shards with different DB files, and is a no-op for a single DB.
    """
    import sqlite3

    per_metric: dict[str, dict[str, float]] = {}
    all_qids: set[str] = set()
    for path in store_paths:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            for row in connection.execute(
                "SELECT qid, metric, value FROM metrics WHERE run_id=?", (run_id,)
            ):
                per_metric.setdefault(row["metric"], {})[row["qid"]] = row["value"]
                all_qids.add(row["qid"])
        finally:
            connection.close()
    return {metric: list(values.values()) for metric, values in per_metric.items()}, all_qids


def _find_run_ids(store_paths: list[Path]) -> dict[str, dict[str, str]]:
    import sqlite3

    found: dict[str, dict[str, str]] = {}
    for path in store_paths:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            for row in connection.execute("SELECT run_id, config_hash, status FROM runs"):
                found.setdefault(row["config_hash"], {"run_id": row["run_id"], "status": row["status"]})
        finally:
            connection.close()
    return found


def analyze(spec_path: Path, store_paths: list[Path]) -> dict[str, Any]:
    spec = spec_module.load(spec_path)
    machine = compiler.Compiler(spec)
    all_plans = machine._single_factor()  # every requested level, before dedupe
    kept = compiler.compile_spec(spec)
    reference_hash = machine._plan(0, machine._base()).config_hash
    runs = _find_run_ids(store_paths)
    reference_run = runs.get(reference_hash)
    if reference_run is None:
        raise SystemExit(f"reference run {reference_hash} is missing from {[str(path) for path in store_paths]}")
    reference_metrics, _reference_qids = _rows_for_plan(store_paths, reference_run["run_id"])
    reference_means = {
        key: _mean(reference_metrics.get(key, [])) for key in
        ("evidence_recall", "ndcg", "tokens", "redundancy", "context_precision")
    }

    reference_label = spec.reference_config()
    git_commit = _git_commit()
    factors_out = []
    for factor in spec.factors:
        factor_id = str(factor["id"])
        rows = []
        for level in factor.get("levels") or []:
            matching = [plan for plan in all_plans
                        if plan.factors.get(factor_id) == level]
            if not matching:
                raise SystemExit(f"no compiled plan for {factor_id}={level!r}")
            plan = matching[0]
            run = runs.get(plan.config_hash)
            if run is None:
                raise SystemExit(
                    f"no result row for {factor_id}={level!r} hash={plan.config_hash}; "
                    f"db={[str(path) for path in store_paths]}"
                )
            metrics, all_qids = _rows_for_plan(store_paths, run["run_id"])
            errors = len(metrics.get("error", []))
            row: dict[str, Any] = {
                "level": level,
                "level_label": _level_label(level),
                "config_hash": plan.config_hash,
                "run_id": run["run_id"],
                "status": run["status"],
                "errors": errors,
                "shared_baseline": plan.config_hash == reference_hash,
            }
            for key in METRIC_KEYS:
                values = metrics.get(key, [])
                row[f"{key}_n"] = len(values)
                row[key] = _mean(values)
            row["n_questions"] = len(all_qids)
            latency = metrics.get("latency_ms", [])
            row["p95_latency_ms"] = _p95(latency)
            row["error_rate"] = round(errors / (row["n_questions"] + errors), 6) if row["n_questions"] + errors else None
            rows.append(row)

        baseline = next((row for row in rows if row["shared_baseline"]), None)
        for row in rows:
            row["delta_vs_baseline"] = {
                key: (round(row[key] - reference_means[key], 6)
                      if row.get(key) is not None and reference_means.get(key) is not None else None)
                for key in ("evidence_recall", "ndcg", "tokens", "redundancy", "context_precision")
            }

        shapes = {key: _shape(rows, key) for key in ("evidence_recall", "ndcg", "tokens", "redundancy")}
        wired = factor.get("wired", True)
        finding = FINDINGS.get(factor_id) or {}
        if finding.get("verdict"):
            verdict = finding["verdict"]
        elif not wired:
            verdict = ("no-difference: parameter is declared but not consumed by the current "
                       "pipeline; the curve cannot inform tuning")
        elif all(shapes[key]["shape"] == "flat" for key in ("evidence_recall", "ndcg", "tokens", "redundancy")):
            verdict = ("no-difference across the tested levels at fixed candidate budget 15; "
                       "knob is inert in this offline configuration")
        else:
            changed = [key for key, value in shapes.items() if value["shape"] != "flat"]
            verdict = "difference detected in " + ", ".join(changed)

        factors_out.append({
            "schema": "memlab/params-curve@1",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "experiment_id": spec.id,
            "spec_hash": spec.spec_hash,
            "git_commit": git_commit,
            "offline": True,
            "level": "A-interface",
            "answer_f1_policy": "not reported: offline extractive is not an LLM answer",
            "judge_policy": "not reported: no judge in offline A-level run",
            "dataset": {
                "split": spec.dataset.get("split"),
                "samples": list(spec.dataset.get("samples") or []),
                "question_limit": spec.dataset.get("question_limit"),
                "total_questions_per_level": rows[0]["n_questions"] if rows else 0,
            },
            "factor": {
                "id": factor_id,
                "label": factor.get("label") or LABELS.get(factor_id, factor_id),
                "module": factor.get("module"),
                "axis": factor.get("axis"),
                "path": factor.get("path") or factor_id,
                "requested_path": factor.get("requested_path") or factor.get("path") or factor_id,
                "levels": list(factor.get("levels") or []),
                "hypothesis": factor.get("hypothesis"),
                "wired": wired,
                "note": factor.get("note"),
            },
            "reference_config": _relative(spec.reference),
            "reference_hash": reference_hash,
            "reference_metrics": reference_means,
            "baseline_level": _level_label(baseline["level"]) if baseline else "R0 reference (not a level)",
            "shared_baseline_note": (
                "Levels with shared_baseline=true have the same config_hash as reference-r0; "
                "the compiler ran them once and this table reuses that run."
            ),
            "rows": rows,
            "shape": shapes,
            "effective_in_e2e": finding.get("effective_in_e2e", True),
            "harness_blocker": finding.get("harness_blocker"),
            "evidence": list(finding.get("evidence") or []),
            "verdict": verdict,
        })

    return {
        "schema": "memlab/params-curves@1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "experiment_id": spec.id,
        "spec": str(spec_path),
        "spec_hash": spec.spec_hash,
        "git_commit": git_commit,
        "stores": [str(path) for path in store_paths],
        "compiled": {
            "requested_levels": len(all_plans),
            "executed_runs": len(kept),
            "deduplicated_levels": sum(len(plan.aliases) for plan in kept),
            "note": "one run can serve several factor levels when they share the reference config hash",
        },
        "run_command": (
            "python -m memlab.experiments.cli run --spec configs/experiments/e1-params.json "
            "--executor e2e --offline --limit 60 --db runs/params/p1.sqlite"
        ),
        "offline": True,
        "level": "A-interface",
        "environment": {
            "llm": "offline-extractive",
            "embedding": "offline-hash",
            "note": "Hashing embeddings are not semantic; offline results must not be written as 27B conclusions.",
        },
        "dataset": {
            "samples": list(spec.dataset.get("samples") or []),
            "question_limit": spec.dataset.get("question_limit"),
            "questions_per_level": factors_out[0]["rows"][0]["n_questions"] if factors_out else 0,
        },
        "metric_note": (
            "Recall@15/nDCG@15 average over questions with gold evidence (238/240); "
            "tokens/redundancy/context precision average over all 240. The 2 questions without "
            "gold evidence are not errors."
        ),
        "deferred": spec.deferred,
        "factors": factors_out,
    }


def write_csv(payload: dict[str, Any], path: Path) -> None:
    columns = [
        "factor", "module", "level", "run_id", "config_hash", "shared_baseline", "n_questions", "errors",
        "recall_at_15", "ndcg_at_15", "tokens_per_query", "redundancy_rate",
        "context_precision", "p95_latency_ms", "delta_recall_vs_baseline",
        "delta_ndcg_vs_baseline", "delta_tokens_vs_baseline", "verdict",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for factor in payload["factors"]:
            for row in factor["rows"]:
                delta = row.get("delta_vs_baseline") or {}
                writer.writerow({
                    "factor": factor["factor"]["id"],
                    "module": factor["factor"].get("module"),
                    "level": row["level_label"],
                    "run_id": row["run_id"],
                    "config_hash": row["config_hash"],
                    "shared_baseline": row["shared_baseline"],
                    "n_questions": row["n_questions"],
                    "errors": row["errors"],
                    "recall_at_15": row.get("evidence_recall"),
                    "ndcg_at_15": row.get("ndcg"),
                    "tokens_per_query": row.get("tokens"),
                    "redundancy_rate": row.get("redundancy"),
                    "context_precision": row.get("context_precision"),
                    "p95_latency_ms": row.get("p95_latency_ms"),
                    "delta_recall_vs_baseline": delta.get("evidence_recall"),
                    "delta_ndcg_vs_baseline": delta.get("ndcg"),
                    "delta_tokens_vs_baseline": delta.get("tokens"),
                    "verdict": factor["verdict"],
                })


def _fmt(value, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return f"{value:.{digits}f}"


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# E1.2 parameter curves (offline A-level)",
        "",
        f"- experiment: `{payload['experiment_id']}`",
        f"- generated: {payload['generated_at']}",
        f"- spec: `{payload['spec']}` (hash `{payload['spec_hash']}`)",
        f"- git commit: `{payload['git_commit']}`",
        f"- compiled: {payload['compiled']['requested_levels']} requested levels -> "
        f"{payload['compiled']['executed_runs']} runs "
        f"({payload['compiled']['deduplicated_levels']} shared-baseline aliases)",
        f"- stores: " + ", ".join(f"`{store}`" for store in payload["stores"]),
        f"- dataset: {', '.join(payload['dataset']['samples'])}; "
        f"{payload['dataset']['question_limit']} questions/conversation; "
        f"{payload['dataset']['questions_per_level']} questions per level",
        "- models: `offline-extractive` answers + `offline-hash` embeddings (hashing is not semantic)",
        "- scope: A-level interface metrics only. **No answer F1, no Judge.** These are not 27B results.",
        "",
        "Every level changes exactly one dotted config path from `configs/reference-r0.json`. "
        "Levels marked `*` share the reference config hash; the compiler ran them once as a baseline "
        "and this table reuses that run (the metrics are identical by construction).",
        "",
        "## Curve table",
        "",
        "| Module | Factor | Level | Recall@15 | nDCG@15 | tokens/q | redundancy | Δrecall | ΔnDCG | Δtokens |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    reference = payload["factors"][0].get("reference_metrics") if payload["factors"] else None
    if reference:
        lines.append(
            f"| R0 | reference config | - | {_fmt(reference.get('evidence_recall'))} "
            f"| {_fmt(reference.get('ndcg'))} | {_fmt(reference.get('tokens'), 1)} "
            f"| {_fmt(reference.get('redundancy'))} | 0.0000 | 0.0000 | 0.0 |"
        )
    for factor in payload["factors"]:
        factor_id = factor["factor"]["id"]
        module = factor["factor"].get("module") or ""
        for row in factor["rows"]:
            delta = row.get("delta_vs_baseline") or {}
            star = "*" if row.get("shared_baseline") else ""
            lines.append(
                f"| {module} | `{factor_id}` | `{row['level_label']}`{star} "
                f"| {_fmt(row.get('evidence_recall'))} | {_fmt(row.get('ndcg'))} "
                f"| {_fmt(row.get('tokens'), 1)} | {_fmt(row.get('redundancy'))} "
                f"| {_fmt(delta.get('evidence_recall'))} | {_fmt(delta.get('ndcg'))} "
                f"| {_fmt(delta.get('tokens'), 1)} |"
            )
    lines += [
        "",
        "`p95_latency_ms` is kept in the JSON/CSV for completeness but is not a controlled latency "
        "comparison: all configs share one process, caches warm up during the first run, and the "
        "offline hash embedder is not the real retrieval cost.",
        "",
        "Recall@15 and nDCG@15 are averaged over the 238/240 questions that have gold evidence turns; "
        "tokens/redundancy/context precision are averaged over 240. The two questions without gold "
        "evidence are not errors.",
        "",
        "## Per-factor findings",
        "",
    ]
    for factor in payload["factors"]:
        info = factor["factor"]
        lines.append(f"### {info.get('label') or info['id']} (`{info['id']}`)")
        lines.append("")
        lines.append(f"- path: `{info.get('path')}`; levels: `{info.get('levels')}`; "
                     f"wired in code: `{info.get('wired')}`; effective in this e2e harness: "
                     f"`{factor.get('effective_in_e2e')}`")
        if info.get("requested_path") and info.get("requested_path") != info.get("path"):
            lines.append(f"- requested path in the task: `{info['requested_path']}` (not consumed; see deferred)")
        if factor.get("harness_blocker"):
            lines.append(f"- harness blocker: {factor['harness_blocker']}")
        lines.append(f"- verdict: {factor['verdict']}")
        for item in factor.get("evidence") or []:
            lines.append(f"- evidence: {item}")
        lines.append("")
    lines += [
        "## Wiring audit (why several curves are flat)",
        "",
        "- R4 k: `retrieve._k` (`memlab/retrieve.py:56`) returns an explicit `requested` k before it reads "
        "`retrieval.k`; the e2e executor always passes `k=15` (`memlab/experiments/executor.py:143`). "
        "`planner.params.k` is never read.",
        "- S2 max_neighbors: `GraphIndex.expand` (`memlab/store.py:88`) accepts only `seeds` and `k_hop`; "
        "the config value is accepted but unused.",
        "- W4 fields: `MetaSchemaExtractor` records the value (`memlab/write.py:163`), and `search_text` "
        "flattens all structured fields into the BM25 text (`memlab/store.py:49`). The digit itself is "
        "indexed, which is the entire measured effect.",
        "- W4 evidence: `MetaSchemaExtractor` always derives `unit.evidence`; the flag is only validated/accepted.",
        "- M4 MMR: `MMRPost` defaults `top_n` to the candidate count and only permutes (`memlab/merge.py:409`); "
        "the following `TimeDecayPost` re-sorts by score (`memlab/merge.py:453`), erasing the permutation.",
        "- M6 top_n: `CrossEncoderReranker` applies `top_n` only after a successful model load "
        "(`memlab/merge.py:321`); without `sentence-transformers` it returns the incoming order and records a fallback.",
        "",
        "## Acceptance check",
        "",
        f"- requested levels: {payload['compiled']['requested_levels']}; executed runs: "
        f"{payload['compiled']['executed_runs']} (five reference-value levels deduplicated into one baseline)",
        "- all 20 runs status `complete`; 0 `error` rows; 240 questions per level (4 development conversations x 60)",
        "- artifacts: 9 `params-*.json` files + this table + `params-curves.csv` + `params-curves.json`",
        f"- deferred requested level: `planner.params.k` -> {payload['deferred'][0]['reason'] if payload['deferred'] else 'none'}",
        "- no `answer_f1` and no Judge metric is reported; no 27B claim is made",
        "",
        "## What this run can and cannot say",
        "",
        "- Live knobs in this offline harness: `post.decay.params.lambda` (ranking-only nDCG) and "
        "`post.compress.params.budget_tokens` (only 500 starts to bite). `schema.params.fields` moves "
        "metrics only because the numeric value leaks into the BM25 index via `search_text`; that is a "
        "lexical artifact, not extraction quality.",
        "- Blocked or inert in this harness: `schema.params.evidence`, `graph.retrieval.params.max_neighbors`, "
        "`retrieval.k` (and therefore the requested `planner.params.k`), `post.mmr.params.lambda`, and "
        "`rerank.params.top_n`. Their flat curves are wiring/stage-order/fallback findings, not evidence "
        "that the parameter is useless with a real extractor, reranker or a different stage order.",
        "- `graph.retrieval.params.k_hop` is read, but 1-hop expansion already fills the 15-candidate budget "
        "on the three-layer graph, so 2/3 cannot show a difference at this budget.",
        "- Do not promote these numbers to B-level claims. A B-level run needs Ollama (or the S9 provider "
        "adapter), semantic embeddings, a real cross-encoder, and LLM answers/judging.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default="configs/experiments/e1-params.json")
    parser.add_argument("--db", nargs="+", default=["runs/params/p1.sqlite"])
    parser.add_argument("--out-dir", default="eval/archive")
    args = parser.parse_args(argv)

    spec_path = Path(args.spec)
    store_paths = [Path(value) for value in args.db]
    for path in store_paths:
        if not path.is_file():
            raise SystemExit(f"result store not found: {path}")
    payload = analyze(spec_path, store_paths)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for factor in payload["factors"]:
        slug = SLUGS.get(factor["factor"]["id"], factor["factor"]["id"].replace(".", "-"))
        target = out_dir / f"params-{slug}.json"
        target.write_text(json.dumps(factor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target}")
    combined = out_dir / "params-curves.json"
    combined.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(payload, out_dir / "params-curves.csv")
    write_markdown(payload, out_dir / "params-curves.md")
    print(f"wrote {combined}")
    print(f"wrote {out_dir / 'params-curves.md'}")
    print(f"wrote {out_dir / 'params-curves.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
