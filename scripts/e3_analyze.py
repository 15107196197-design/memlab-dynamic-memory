#!/usr/bin/env python3
"""Analyze the E3 2^(5-1) resolution-V half-fraction (offline A-level).

The design is saturated (16 runs = intercept + 5 main effects + 10 two-way
interactions).  We therefore estimate main effects and two-way interactions as
orthogonal contrasts, and state explicitly that each two-way estimate is aliased
with a three-way interaction (resolution V), not with another two-way effect.
Confidence intervals are conversation-cluster bootstrap intervals, not model
residual intervals.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FACTORS = ["schema", "graph", "planner", "rerank", "fusion"]
METRICS = ["evidence_recall", "ndcg", "tokens", "redundancy", "context_precision"]
QUALITY = {"evidence_recall", "ndcg", "context_precision", "redundancy"}
PAIRS = [(a, b) for i, a in enumerate(FACTORS) for b in FACTORS[i + 1:]]
# Generator I = ABCDE; each 2FI is aliased with the complementary 3FI.
ALIASES = {
    "schema+graph": "planner+rerank+fusion",
    "schema+planner": "graph+rerank+fusion",
    "schema+rerank": "graph+planner+fusion",
    "schema+fusion": "graph+planner+rerank",
    "graph+planner": "schema+rerank+fusion",
    "graph+rerank": "schema+planner+fusion",
    "graph+fusion": "schema+planner+rerank",
    "planner+rerank": "schema+graph+fusion",
    "planner+fusion": "schema+graph+rerank",
    "rerank+fusion": "schema+graph+planner",
}


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
    for row in connection.execute("SELECT run_id, factors_json, dataset_json, status FROM runs"):
        runs[row["run_id"]] = {
            "factors": json.loads(row["factors_json"] or "{}"),
            "dataset": json.loads(row["dataset_json"] or "{}"),
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


def conv_means(per_run):
    """run -> metric -> conversation -> mean."""
    out = {}
    for run_id, metrics in per_run.items():
        out[run_id] = {}
        for metric, values in metrics.items():
            grouped = {}
            for qid, value in values.items():
                conversation = qid.split(":", 1)[0]
                grouped.setdefault(conversation, []).append(value)
            out[run_id][metric] = {conversation: mean(items) for conversation, items in grouped.items()}
    return out


def run_means(per_run):
    return {
        run_id: {metric: mean(list(values.values())) for metric, values in metrics.items()}
        for run_id, metrics in per_run.items()
    }


def cluster_bootstrap(values_by_run, run_ids, conversations, *, samples=1000, seed=13):
    """Bootstrap a mean over run_ids, resampling conversations (clusters)."""
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        picked = [rng.choice(conversations) for _ in conversations]
        run_values = []
        for run_id in run_ids:
            per_conv = values_by_run[run_id]
            available = [per_conv[c] for c in picked if per_conv.get(c) is not None]
            if available:
                run_values.append(mean(available))
        if run_values:
            draws.append(mean(run_values))
    return draws


def contrast_ci(values_by_run, high_ids, low_ids, conversations, *, samples=1000, seed=13):
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        picked = [rng.choice(conversations) for _ in conversations]
        high_values, low_values = [], []
        for run_id in high_ids:
            per_conv = values_by_run[run_id]
            available = [per_conv[c] for c in picked if per_conv.get(c) is not None]
            if available:
                high_values.append(mean(available))
        for run_id in low_ids:
            per_conv = values_by_run[run_id]
            available = [per_conv[c] for c in picked if per_conv.get(c) is not None]
            if available:
                low_values.append(mean(available))
        if high_values and low_values:
            draws.append(mean(high_values) - mean(low_values))
    return draws


def interaction_ci(values_by_run, cell_ids, conversations, *, samples=1000, seed=13):
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        picked = [rng.choice(conversations) for _ in conversations]
        cell_values = {}
        for cell, run_ids in cell_ids.items():
            run_values = []
            for run_id in run_ids:
                per_conv = values_by_run[run_id]
                available = [per_conv[c] for c in picked if per_conv.get(c) is not None]
                if available:
                    run_values.append(mean(available))
            if run_values:
                cell_values[cell] = mean(run_values)
        if len(cell_values) == 4:
            draws.append(cell_values[(1, 1)] - cell_values[(1, 0)] - cell_values[(0, 1)] + cell_values[(0, 0)])
    return draws


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="runs/e3-offline/e3.sqlite")
    parser.add_argument("--out", default="eval/archive/e3-offline.json")
    parser.add_argument("--samples", type=int, default=1000)
    args = parser.parse_args(argv)

    db = Path(args.db)
    runs, per_run, errors = read_store(db)
    cmeans = conv_means(per_run)
    rmeans = run_means(per_run)
    conversations = sorted({qid.split(":", 1)[0] for metrics in per_run.values()
                            for values in metrics.values() for qid in values}) or ["conv-26"]
    factors_by_run = {run_id: info["factors"] for run_id, info in runs.items()}
    all_run_ids = sorted(runs)
    if len(all_run_ids) != 16:
        raise SystemExit(f"expected 16 E3 runs, found {len(all_run_ids)}")

    # sanity: each factor should be balanced 8 low / 8 high
    balance = {}
    for factor in FACTORS:
        values = [factors_by_run[run_id].get(factor) for run_id in all_run_ids]
        balance[factor] = {str(value): values.count(value) for value in sorted(set(values), key=str)}

    main_effects = {}
    for metric in METRICS:
        rows = []
        for factor in FACTORS:
            # Explicit low/high names per factor (the values are not interchangeable).
            high_name = {
                "schema": "meta_schema", "graph": "three_layer", "planner": "dag",
                "rerank": "cross_encoder", "fusion": "query_adaptive_weights",
            }[factor]
            low_name = {
                "schema": "legacy_flat", "graph": "state_slot", "planner": "none",
                "rerank": "none", "fusion": "single_channel",
            }[factor]
            high_ids = [r for r in all_run_ids if factors_by_run[r].get(factor) == high_name]
            low_ids = [r for r in all_run_ids if factors_by_run[r].get(factor) == low_name]
            high_value = mean([rmeans[r][metric] for r in high_ids if rmeans[r][metric] is not None])
            low_value = mean([rmeans[r][metric] for r in low_ids if rmeans[r][metric] is not None])
            draw = contrast_ci({r: cmeans[r][metric] for r in all_run_ids},
                               high_ids, low_ids, conversations, samples=args.samples)
            low_ci, high_ci = pct(draw, 0.025), pct(draw, 0.975)
            delta = high_value - low_value if high_value is not None and low_value is not None else None
            rows.append({
                "factor": factor,
                "low": low_name,
                "high": high_name,
                "low_value": round(low_value, 6) if low_value is not None else None,
                "high_value": round(high_value, 6) if high_value is not None else None,
                "delta_high_minus_low": round(delta, 6) if delta is not None else None,
                "ci95": [round(low_ci, 6) if low_ci is not None else None,
                         round(high_ci, 6) if high_ci is not None else None],
                "ci_excludes_zero": bool(low_ci is not None and high_ci is not None and not (low_ci <= 0 <= high_ci)),
                "direction": "lower_is_better_cost" if metric in ("tokens", "redundancy") else "higher_is_better",
            })
        main_effects[metric] = rows

    interactions = []
    for metric in METRICS:
        for left, right in PAIRS:
            cell_ids = {(0, 0): [], (1, 0): [], (0, 1): [], (1, 1): []}
            high_name = {
                "schema": "meta_schema", "graph": "three_layer", "planner": "dag",
                "rerank": "cross_encoder", "fusion": "query_adaptive_weights",
            }
            for run_id in all_run_ids:
                key = (1 if factors_by_run[run_id].get(left) == high_name[left] else 0,
                       1 if factors_by_run[run_id].get(right) == high_name[right] else 0)
                cell_ids[key].append(run_id)
            if any(not ids for ids in cell_ids.values()):
                raise SystemExit(f"design does not contain all four cells for {left}+{right}")
            cell_values = {
                cell: mean([rmeans[r][metric] for r in ids if rmeans[r][metric] is not None])
                for cell, ids in cell_ids.items()
            }
            interaction = (cell_values[(1, 1)] - cell_values[(1, 0)]
                           - cell_values[(0, 1)] + cell_values[(0, 0)])
            draw = interaction_ci({r: cmeans[r][metric] for r in all_run_ids},
                                  cell_ids, conversations, samples=args.samples)
            low_ci, high_ci = pct(draw, 0.025), pct(draw, 0.975)
            additive_gain = (cell_values[(1, 0)] - cell_values[(0, 0)]) + (cell_values[(0, 1)] - cell_values[(0, 0)])
            joint_gain = cell_values[(1, 1)] - cell_values[(0, 0)]
            interactions.append({
                "pair": f"{left}+{right}",
                "alias": ALIASES[f"{left}+{right}"],
                "metric": metric,
                "y00": round(cell_values[(0, 0)], 6),
                "y10": round(cell_values[(1, 0)], 6),
                "y01": round(cell_values[(0, 1)], 6),
                "y11": round(cell_values[(1, 1)], 6),
                "joint_gain_y11_minus_y00": round(joint_gain, 6),
                "additive_gain": round(additive_gain, 6),
                "interaction": round(interaction, 6),
                "ci95": [round(low_ci, 6) if low_ci is not None else None,
                         round(high_ci, 6) if high_ci is not None else None],
                "ci_excludes_zero": bool(low_ci is not None and high_ci is not None and not (low_ci <= 0 <= high_ci)),
                "interpretation": (
                    "super_additive" if interaction > 0 else "sub_additive"
                ) if metric in QUALITY else (
                    "super_additive_cost" if interaction > 0 else "sub_additive_cost"
                ),
                "note": "2FI is aliased with the complementary 3FI (resolution V); no residual df.",
            })

    run_rows = []
    for run_id in all_run_ids:
        info = runs[run_id]
        run_rows.append({
            "run_id": run_id,
            "factors": info["factors"],
            "status": info["status"],
            "errors": errors.get(run_id, 0),
            "n_questions": len(per_run[run_id]["tokens"]),
            **{metric: round(rmeans[run_id][metric], 6) if rmeans[run_id][metric] is not None else None
               for metric in METRICS},
        })

    payload = {
        "schema": "memlab/e3-analysis@1",
        "experiment_id": "E3-module-combinations",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "offline": True,
        "level": "A-interface",
        "answer_f1_policy": "not reported: offline extractive is not an LLM answer",
        "judge_policy": "not reported: no judge in offline A-level run",
        "source_db": str(db),
        "dataset": {
            "samples": sorted(conversations),
            "questions_per_run": len(per_run[all_run_ids[0]]["tokens"]),
            "question_limit_per_conversation": 60,
        },
        "design": {
            "type": "2^(5-1) fractional factorial",
            "resolution": "V",
            "generator": "I = ABCDE (fusion = schema*graph*planner*rerank parity)",
            "factors": FACTORS,
            "runs": 16,
            "balance": balance,
            "aliasing": ALIASES,
            "center_points": "spec mentions 4 center points, but the S5 compiler does not execute them; this run has 16 runs only.",
            "note": "Resolution V: main effects are clear of 2FIs; each 2FI is aliased with a 3FI, not with another 2FI. The design is saturated (16 parameters for 16 runs), so no residual df; CIs are conversation-cluster bootstrap, not model-residual CIs.",
        },
        "runs": run_rows,
        "main_effects": main_effects,
        "interactions": interactions,
        "limitations": [
            "Offline hash embedding is not semantic; offline extractive answer is not an LLM answer.",
            "All metrics are A-level interface metrics; no answer F1 and no Judge.",
            "Only 4 development conversations, 60 questions per conversation per run.",
            "Resolution V 2FIs assume 3FIs are negligible; no residual df.",
            "Several implementation axes are no-op or harness-blocked (e.g. rerank cross-encoder may fall back, graph channel is rarely used); a flat effect is not evidence of no effect with a real model.",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")

    # compact stdout summary
    for metric in ("evidence_recall", "ndcg", "tokens"):
        print(f"\n{metric} main effects (high-low):")
        for row in main_effects[metric]:
            print(f"  {row['factor']:8s} {row['delta_high_minus_low']:+.4f} "
                  f"CI={row['ci95']} {'*' if row['ci_excludes_zero'] else ''}")
    print("\nTop |interaction| (quality metrics):")
    quality_rows = [r for r in interactions if r["metric"] in ("evidence_recall", "ndcg")]
    for row in sorted(quality_rows, key=lambda item: abs(item["interaction"]), reverse=True)[:8]:
        print(f"  {row['metric']:16s} {row['pair']:16s} {row['interaction']:+.4f} "
              f"CI={row['ci95']} {row['interpretation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
