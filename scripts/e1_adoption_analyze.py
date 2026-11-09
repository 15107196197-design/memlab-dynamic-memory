#!/usr/bin/env python3
"""Analyze E1.1 strict single-factor adoption (add/remove one component).

`single_factor_adoption` produces add-from-B0 and remove-from-R0 runs.  This
script adds the missing standalone B0/R0 deltas from the same DB and reports
paired conversation-cluster bootstrap CIs.  It is A-level only: no answer F1,
no Judge, and the offline extractive answer is not an LLM answer.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

METRICS = ["evidence_recall", "ndcg", "tokens", "redundancy", "context_precision"]
LOWER_BETTER = {"tokens", "redundancy"}


def mean(values):
    return statistics.fmean(values) if values else None


def pct(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def read_store(path: Path):
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    runs = {}
    for row in connection.execute("SELECT run_id, factors_json, status FROM runs"):
        runs[row["run_id"]] = {
            "factors": json.loads(row["factors_json"] or "{}"),
            "status": row["status"],
        }
    per_run = {run_id: {metric: {} for metric in METRICS} for run_id in runs}
    for row in connection.execute(
        "SELECT run_id, qid, metric, value FROM metrics WHERE metric IN (%s)"
        % ",".join("?" for _ in METRICS), METRICS
    ):
        per_run[row["run_id"]][row["metric"]][row["qid"]] = row["value"]
    errors = {
        row["run_id"]: row["n"]
        for row in connection.execute(
            "SELECT run_id, COUNT(*) AS n FROM metrics WHERE metric='error' GROUP BY run_id"
        )
    }
    connection.close()
    return runs, per_run, errors


def conversation_means(per_run):
    out = {}
    for run_id, metrics in per_run.items():
        out[run_id] = {}
        for metric, values in metrics.items():
            grouped = {}
            for qid, value in values.items():
                grouped.setdefault(qid.split(":", 1)[0], []).append(value)
            out[run_id][metric] = {conv: mean(items) for conv, items in grouped.items()}
    return out


def paired_delta_ci(run_means, base_means, conversations, *, samples=1000, seed=13):
    """Paired delta (candidate - base) with conversation-cluster bootstrap."""
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        picked = [rng.choice(conversations) for _ in conversations]
        diffs = []
        for conv in picked:
            candidate = run_means.get(conv)
            base = base_means.get(conv)
            if candidate is not None and base is not None:
                diffs.append(candidate - base)
        if diffs:
            draws.append(mean(diffs))
    return draws


def summarize_run(per_run, run_id, metric):
    values = list(per_run[run_id][metric].values())
    return mean(values)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="runs/adoption/adoption.sqlite")
    parser.add_argument("--out", default="eval/archive/e1-adoption-offline.json")
    parser.add_argument("--samples", type=int, default=1000)
    args = parser.parse_args(argv)

    db = Path(args.db)
    runs, per_run, errors = read_store(db)
    cmeans = conversation_means(per_run)
    conversations = sorted({qid.split(":", 1)[0] for metrics in per_run.values()
                            for values in metrics.values() for qid in values})
    baseline_ids = {
        info["factors"].get("baseline"): run_id
        for run_id, info in runs.items()
        if info["factors"].get("module") == "__baseline__"
    }
    if "B0" not in baseline_ids or "R0" not in baseline_ids:
        raise SystemExit("B0/R0 baselines missing; run scripts/e1_adoption_baselines.py first")

    modules = []
    for module in sorted({info["factors"].get("module") for info in runs.values()
                          if info["factors"].get("module") not in (None, "__baseline__")}):
        add_id = next((run_id for run_id, info in runs.items()
                       if info["factors"].get("module") == module
                       and info["factors"].get("baseline") == "add_from_B0"), None)
        remove_id = next((run_id for run_id, info in runs.items()
                          if info["factors"].get("module") == module
                          and info["factors"].get("baseline") == "remove_from_R0"), None)
        entry = {"module": module, "add_from_B0": None, "remove_from_R0": None}
        for side, run_id, base_key in (("add_from_B0", add_id, "B0"),
                                       ("remove_from_R0", remove_id, "R0")):
            if run_id is None:
                entry[side] = {"status": "not_in_compiled_matrix"}
                continue
            base_id = baseline_ids[base_key]
            metrics = {}
            for metric in METRICS:
                candidate_value = summarize_run(per_run, run_id, metric)
                base_value = summarize_run(per_run, base_id, metric)
                delta = (candidate_value - base_value
                         if candidate_value is not None and base_value is not None else None)
                draw = paired_delta_ci(cmeans[run_id][metric], cmeans[base_id][metric],
                                       conversations, samples=args.samples)
                low, high = pct(draw, 0.025), pct(draw, 0.975)
                metrics[metric] = {
                    "candidate": round(candidate_value, 6) if candidate_value is not None else None,
                    "baseline": round(base_value, 6) if base_value is not None else None,
                    "delta": round(delta, 6) if delta is not None else None,
                    "ci95": [round(low, 6) if low is not None else None,
                             round(high, 6) if high is not None else None],
                    "ci_excludes_zero": bool(low is not None and high is not None and not (low <= 0 <= high)),
                    "pct_change": (round(100 * delta / base_value, 3)
                                   if delta is not None and base_value not in (None, 0) else None),
                    "direction": "lower_is_better" if metric in LOWER_BETTER else "higher_is_better",
                }
            entry[side] = {
                "run_id": run_id,
                "status": runs[run_id]["status"],
                "errors": errors.get(run_id, 0),
                "baseline_run_id": base_id,
                "n_questions": len(per_run[run_id]["tokens"]),
                "metrics": metrics,
            }
        modules.append(entry)

    payload = {
        "schema": "memlab/e1-adoption@1",
        "experiment_id": "E1.1-module-adoption",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "offline": True,
        "level": "A-interface",
        "answer_f1_policy": "not reported: offline extractive is not an LLM answer",
        "judge_policy": "not reported: no judge in offline A-level run",
        "source_db": str(db),
        "dataset": {
            "samples": conversations,
            "questions_per_run": len(per_run[baseline_ids["B0"]]["tokens"]),
            "question_limit_per_conversation": 60,
        },
        "protocol": {
            "design": "single_factor_adoption: add one component from B0, remove one component from R0",
            "paired_by": "conversation",
            "bootstrap_samples": args.samples,
            "ci": "95% percentile, conversation-cluster bootstrap",
        },
        "baselines": {
            key: {
                "run_id": run_id,
                "metrics": {metric: round(summarize_run(per_run, run_id, metric), 6)
                            for metric in METRICS},
            }
            for key, run_id in baseline_ids.items()
        },
        "modules": modules,
        "limitations": [
            "Offline hash embedding is not semantic; offline extractive answer is not an LLM answer.",
            "A-level interface metrics only; no answer F1, no Judge.",
            "S6 'A' candidates are bundles of several components; these runs are strict one-component add/remove and must not be compared as if they were the same factor.",
            "Some component axes are no-op or fall back offline (e.g. cross-encoder, LLM audit); a zero delta is not evidence of no effect with a real model.",
            "B0 and R0 are separate baselines: add-from-B0 and remove-from-R0 deltas are not directly comparable to each other.",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")

    print("\nmodule                   add_delta_recall  add_ci               remove_delta_recall  remove_ci")
    for entry in modules:
        add = entry["add_from_B0"]
        remove = entry["remove_from_R0"]
        def fmt(side):
            if side.get("status") != "complete":
                return "-", "-"
            item = side["metrics"]["evidence_recall"]
            return f"{item['delta']:+.4f}", f"{item['ci95']}"
        add_delta, add_ci = fmt(add)
        remove_delta, remove_ci = fmt(remove)
        print(f"{entry['module']:24s} {add_delta:>16s}  {add_ci:<20s} {remove_delta:>18s}  {remove_ci}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
