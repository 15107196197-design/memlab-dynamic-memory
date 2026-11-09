#!/usr/bin/env python3
"""Export the online E3 2x2 and M2 rerank SQLite runs to experiment-report JSON.

Run from the repository root with no arguments::

    python3 scripts/export_online_extras.py

It reads (never writes) the two local SQLite stores and writes:

    eval/archive/e3-online-2x2.json
    eval/archive/m2-online-rerank.json

Design notes
------------
* SQLite is opened with ``mode=ro``.
* Output is atomic (temp file + ``replace``) and deterministic; re-running on
  the same DB produces byte-identical JSON (``created_at`` is the newest run
  ``updated_at`` rather than wall-clock time).
* No bootstrap CI is computed.  ``ci95`` is therefore ``null`` for every
  comparison and every conclusion is ``inconclusive`` (descriptive only).
* Tokens/seconds are per-question means, not totals.  ``p95_latency_ms`` is
  the run-level p95 of per-question ``latency_ms`` (linear interpolation).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Per-run metric payload required by the handoff.
RUN_METRICS = ["answer_f1", "evidence_recall", "ndcg", "tokens", "seconds", "p95_latency_ms"]
# Metrics compared pairwise (p95 is run-level, so it is not part of paired deltas).
COMPARISON_METRICS = ["answer_f1", "evidence_recall", "ndcg", "tokens", "seconds"]
LOWER_IS_BETTER = {"tokens", "seconds", "p95_latency_ms"}

SPLIT = "development"
SAMPLES = ["conv-26", "conv-30", "conv-43", "conv-44"]
NO_CI_NOTE = "descriptive; n=40 (M2) / 60 per cell (E3); no CI"
ONLINE_LIMITATION = "online 27B, context 8192, development split"

DEFAULTS = {
    "e3": {
        "db": "runs/e3/2x2.sqlite",
        "experiment_id": "E3-online-2x2",
        "out": "eval/archive/e3-online-2x2.json",
        "expected_runs": 4,
        "expected_questions": 60,
    },
    "m2": {
        "db": "runs/s6/m2.sqlite",
        "experiment_id": "M2-online-rerank",
        "out": "eval/archive/m2-online-rerank.json",
        "expected_runs": 2,
        "expected_questions": 40,
    },
}


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
    """Linear-interpolation percentile (same convention as numpy's default)."""
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _read_runs(connection: sqlite3.Connection) -> list[dict]:
    runs = []
    for row in connection.execute("SELECT * FROM runs ORDER BY run_id"):
        runs.append(
            {
                "run_id": row["run_id"],
                "spec_id": row["spec_id"],
                "design": row["design"],
                "config_hash": row["config_hash"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "config": _loads(row["config_json"], {}),
                "dataset": _loads(row["dataset_json"], {}),
                "factors": _loads(row["factors_json"], {}),
            }
        )
    return runs


def _read_metrics(connection: sqlite3.Connection, run_id: str):
    """Return ({metric: {qid: value}}, qid set, error-row count)."""
    by_metric: dict[str, dict[str, float]] = {}
    qids: set[str] = set()
    errors = 0
    for row in connection.execute(
        "SELECT qid, metric, value FROM metrics WHERE run_id = ?", (run_id,)
    ):
        qids.add(row["qid"])
        if row["metric"] == "error":
            errors += 1
            continue
        if row["value"] is None:
            continue
        by_metric.setdefault(row["metric"], {})[row["qid"]] = float(row["value"])
    return by_metric, qids, errors


def _cell_label(factors: dict, kind: str) -> str:
    if kind == "e3":
        return f"fusion={factors.get('fusion.impl')}|answer={factors.get('answer.impl')}"
    return f"rerank={factors.get('rerank.impl')}"


def _is_better(metric: str, delta: float) -> bool:
    if abs(delta) <= 1e-12:
        return False
    return delta < 0 if metric in LOWER_IS_BETTER else delta > 0


def _direction(metric: str, delta: float) -> str:
    if abs(delta) <= 1e-12:
        return "same"
    return "better" if _is_better(metric, delta) else "worse"


def _build_run(run: dict, by_metric: dict, qids: set[str], errors: int, kind: str) -> dict:
    summary = {}
    counts = {}
    for metric in RUN_METRICS:
        if metric == "p95_latency_ms":
            latencies = by_metric.get("latency_ms", {})
            summary[metric] = _round(_percentile(latencies.values(), 0.95))
            counts[metric] = len(latencies)
            continue
        values = list(by_metric.get(metric, {}).values())
        summary[metric] = _round(_mean(values))
        counts[metric] = len(values)

    n_questions = len(qids)
    dataset = run["dataset"] or {}
    return {
        "run_id": run["run_id"],
        "spec_id": run["spec_id"],
        "status": run["status"],
        "cell": _cell_label(run["factors"], kind),
        "factors": run["factors"],
        "config_hash": run["config_hash"],
        "n_questions": n_questions,
        "question_limit": dataset.get("question_limit"),
        "metrics": summary,
        "metric_counts": counts,
        "errors": errors,
        "error_rate": _round(errors / n_questions) if n_questions else None,
    }


def _e3_comparisons(enriched: list[dict], maps: dict[str, dict[str, dict[str, float]]]) -> list[dict]:
    """All six cell pairs x comparison metrics, difference of cell means."""
    comparisons = []
    for index, left in enumerate(enriched):
        for right in enriched[index + 1 :]:
            for metric in COMPARISON_METRICS:
                left_values = maps[left["run_id"]].get(metric, {})
                right_values = maps[right["run_id"]].get(metric, {})
                shared = sorted(set(left_values) & set(right_values))
                if not shared:
                    continue
                baseline_mean = _mean(left_values[qid] for qid in shared)
                candidate_mean = _mean(right_values[qid] for qid in shared)
                delta = candidate_mean - baseline_mean
                comparisons.append(
                    {
                        "baseline": left["cell"],
                        "candidate": right["cell"],
                        "baseline_run_id": left["run_id"],
                        "candidate_run_id": right["run_id"],
                        "metric": metric,
                        "baseline_mean": _round(baseline_mean),
                        "candidate_mean": _round(candidate_mean),
                        "delta": _round(delta),
                        "ci95": None,
                        "direction": _direction(metric, delta),
                        "lower_is_better": metric in LOWER_IS_BETTER,
                        "paired_on_qid": True,
                        "n_pairs": len(shared),
                        "method": "difference_of_cell_means",
                    }
                )
    return comparisons


def _m2_comparisons(runs_by_level: dict[str, dict]) -> list[dict]:
    if "none" not in runs_by_level or "cross_encoder" not in runs_by_level:
        return []
    baseline = runs_by_level["none"]
    candidate = runs_by_level["cross_encoder"]
    comparisons = []
    for metric in COMPARISON_METRICS:
        baseline_values = baseline["_by_metric"].get(metric, {})
        candidate_values = candidate["_by_metric"].get(metric, {})
        shared = sorted(set(baseline_values) & set(candidate_values))
        deltas = [candidate_values[qid] - baseline_values[qid] for qid in shared]
        if not deltas:
            continue
        improved = sum(1 for delta in deltas if _is_better(metric, delta))
        worsened = sum(1 for delta in deltas if _is_better(metric, -delta))
        unchanged = len(deltas) - improved - worsened
        mean_delta = _mean(deltas)
        comparisons.append(
            {
                "baseline": "rerank=none",
                "candidate": "rerank=cross_encoder",
                "baseline_run_id": baseline["run_id"],
                "candidate_run_id": candidate["run_id"],
                "metric": metric,
                "baseline_mean": _round(_mean(baseline_values[qid] for qid in shared)),
                "candidate_mean": _round(_mean(candidate_values[qid] for qid in shared)),
                "delta": _round(mean_delta),
                "mean_delta": _round(mean_delta),
                "median_delta": _round(statistics.median(deltas)),
                "improved": improved,
                "worsened": worsened,
                "unchanged": unchanged,
                "n_pairs": len(deltas),
                "ci95": None,
                "direction": _direction(metric, mean_delta),
                "lower_is_better": metric in LOWER_IS_BETTER,
                "paired": True,
                "method": "paired_per_question_delta",
            }
        )
    return comparisons


def _validate(rows: list[dict], kind: str, expected_runs: int, expected_questions: int) -> None:
    if len(rows) != expected_runs:
        raise SystemExit(f"{kind}: expected {expected_runs} runs, found {len(rows)}")
    for row in rows:
        dataset = row["dataset"] or {}
        if list(dataset.get("samples") or []) != SAMPLES:
            raise SystemExit(
                f"{kind}: unexpected samples in {row['run_id']}: {dataset.get('samples')!r}"
            )
        n_questions = len(row["_qids"])
        if n_questions != expected_questions:
            raise SystemExit(
                f"{kind}: expected {expected_questions} questions in {row['run_id']}, "
                f"found {n_questions}"
            )


def export(kind: str, db_path: Path, experiment_id: str, expected_runs: int, expected_questions: int) -> dict:
    db_path = db_path.resolve()
    if not db_path.exists():
        raise SystemExit(f"missing database: {db_path}")

    connection = _connect_readonly(db_path)
    try:
        runs = _read_runs(connection)
        if not runs:
            raise SystemExit(f"no runs in {db_path}")
        for run in runs:
            by_metric, qids, errors = _read_metrics(connection, run["run_id"])
            run["_by_metric"] = by_metric
            run["_qids"] = qids
            run["_errors"] = errors
    finally:
        connection.close()

    _validate(runs, kind, expected_runs, expected_questions)

    enriched = [
        _build_run(run, run["_by_metric"], run["_qids"], run["_errors"], kind) for run in runs
    ]
    maps = {run["run_id"]: run["_by_metric"] for run in runs}

    if kind == "e3":
        comparisons = _e3_comparisons(enriched, maps)
        dataset = {
            "split": SPLIT,
            "samples": SAMPLES,
            "questions_per_cell": expected_questions,
        }
        comparison_note = (
            "E3: difference of the two cell means over shared qids (all six cell pairs); "
            "ci95 is null because no bootstrap was computed (descriptive only)."
        )
    else:
        by_level = {
            run["factors"].get("rerank.impl"): run
            for run in runs
            if run["factors"].get("rerank.impl") is not None
        }
        comparisons = _m2_comparisons(by_level)
        dataset = {
            "split": SPLIT,
            "samples": SAMPLES,
            "questions_per_config": expected_questions,
        }
        comparison_note = (
            "M2: paired per-question deltas (cross_encoder - none) on shared qids; "
            "ci95 is null because no bootstrap was computed (descriptive only)."
        )

    total_errors = sum(entry["errors"] for entry in enriched)
    created_at = max((run["updated_at"] for run in runs if run["updated_at"]), default=None)

    try:
        source_db = db_path.relative_to(ROOT).as_posix()
    except ValueError:
        source_db = db_path.as_posix()

    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": experiment_id,
        "created_at": created_at,
        "source_db": source_db,
        "source_db_sha256": _sha256(db_path),
        "kind": kind,
        "manifest": {
            "spec_id": runs[0]["spec_id"],
            "design": runs[0]["design"],
            "config_hashes": {run["run_id"]: run["config_hash"] for run in runs},
            "executor": "e2e",
            "exported_by": "scripts/export_online_extras.py",
            "read_only_db": True,
        },
        "dataset": dataset,
        "metric_note": (
            "Per-question means; tokens and seconds are mean per question, not totals. "
            "p95_latency_ms is the run-level p95 of per-question latency_ms. "
            "n_questions is the distinct qid count per run; metric_counts shows per-metric coverage "
            "(ndcg/latency are missing on a few qids)."
        ),
        "comparison_method": comparison_note,
        "results": {
            "runs": enriched,
            "n_runs": len(enriched),
            "errors": total_errors,
        },
        "comparisons": comparisons,
        "analysis": {
            "main_effects": [],
            "interactions": [],
            "pareto": [],
            "stage_waterfall": [],
            "failure_breakdown": [],
            "note": (
                "Descriptive export only: pairwise cell means / paired per-question deltas, "
                "no model fit and no bootstrap CI."
            ),
        },
        "conclusion": {
            "status": "inconclusive",
            "note": NO_CI_NOTE,
            "reason": (
                "No bootstrap confidence interval was computed (ci95=null), so no claim can be "
                "marked supported or not_supported; the deltas are reported descriptively."
            ),
            "claims": [],
            "bootstrap": {"computed": False, "iterations": 0, "ci95": None},
            "conditions": [
                "Development split only.",
                "All runs in an experiment use the same fixed question set, so deltas are paired by qid.",
                "Metrics are per-question means; lower is better for tokens, seconds and p95_latency_ms.",
            ],
            "limitations": [
                ONLINE_LIMITATION,
                (
                    "Single run per cell/config (no seed replicates); run-to-run variance is "
                    "not estimated."
                ),
                (
                    "E3 n=60 per cell; M2 n=40 per config. "
                    "No bootstrap CI and no significance test."
                ),
                "p95 latency is run-level and is not part of the paired per-question deltas.",
            ],
            "next_actions": [
                "Add a paired bootstrap (1000 resamples) before making supported/not_supported claims.",
                "Repeat each cell/config with additional seeds to estimate run-to-run variance.",
            ],
        },
        "web": {"route": f"#/experiments/{experiment_id}", "published": False},
    }
    return report


def _write(report: dict, out_path: Path) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_name(out_path.name + ".tmp")
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(out_path)


def _run_one(kind: str, db: str, out: str, experiment_id: str | None, expected_runs: int, expected_questions: int) -> Path:
    db_path = Path(db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    out_path = Path(out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    report = export(
        kind=kind,
        db_path=db_path,
        experiment_id=experiment_id or DEFAULTS[kind]["experiment_id"],
        expected_runs=expected_runs,
        expected_questions=expected_questions,
    )
    _write(report, out_path)
    print(
        f"wrote {out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path} "
        f"({len(report['results']['runs'])} runs, {len(report['comparisons'])} comparisons, "
        f"errors={report['results']['errors']})"
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", choices=["e3", "m2"], default=None, help="export only one experiment")
    parser.add_argument("--db", default=None, type=Path, help="SQLite store (opened read-only)")
    parser.add_argument("--out", default=None, type=Path, help="output JSON path")
    parser.add_argument("--experiment-id", default=None, help="experiment_id written into the report")
    args = parser.parse_args(argv)

    if args.db or args.out or args.experiment_id:
        if not (args.db and args.out and args.kind):
            parser.error("--db/--out require --kind (e3|m2)")
        expected = DEFAULTS[args.kind]
        _run_one(
            args.kind,
            str(args.db),
            str(args.out),
            args.experiment_id,
            expected["expected_runs"],
            expected["expected_questions"],
        )
        return 0

    kinds = [args.kind] if args.kind else ["e3", "m2"]
    for kind in kinds:
        config = DEFAULTS[kind]
        _run_one(
            kind,
            config["db"],
            config["out"],
            config["experiment_id"],
            config["expected_runs"],
            config["expected_questions"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
