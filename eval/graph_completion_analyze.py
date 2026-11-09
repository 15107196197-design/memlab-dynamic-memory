"""G2 graph-completion harness and archive builder.

The S5 runner cannot execute two of the requested graph arms as written:

* ``retrieval.channels`` is validated by ``memlab/config.py`` but no planner
  reads it.  The single-channel arm (E1-R2) is therefore executed here by
  calling each registered ``retrieval.channel`` implementation directly on the
  same plan config/store/questions.  This is still offline and paired, but it
  bypasses fusion by construction and must not be compared with fused cells.
* ``graph.repr.impl=event_sparse`` is a real config switch, so P0-1 goes through
  the normal CLI runner.  The archive still re-runs the pipeline for diagnostics
  (route intents, channel candidate overlap, graph-novel survival).

Everything is deterministic offline: hashing embedding + extractive answers.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memlab import merge, registry  # noqa: E402
from memlab.contracts import PlanNode  # noqa: E402
from memlab.e2e import E2EPipeline  # noqa: E402
from memlab.experiments import compiler, runner  # noqa: E402
from memlab.experiments import spec as spec_module  # noqa: E402
from memlab.experiments.executor import build_context  # noqa: E402
from memlab.experiments.store import ResultStore  # noqa: E402
from memlab.retrieve import RuleAnalyzer  # noqa: E402
from memwb import evaluation  # noqa: E402

RUNS = ROOT / "runs" / "graph-completion"
ARCHIVE = ROOT / "eval" / "archive" / "graph-completion.json"
P1_DB = RUNS / "single-channel.sqlite"
P1_SPEC = ROOT / "configs" / "experiments" / "g2-e1-r2-single-channel.json"
K = 15


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return round(statistics.mean(clean), 4) if clean else None


def _p95(values: Iterable[float | None]) -> float | None:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return None
    index = min(len(clean) - 1, math.ceil(0.95 * len(clean)) - 1)
    return round(clean[index], 4)


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _gold(question: runner.Question) -> list[str]:
    return evaluation.evidence_turns(question.qa)


# --------------------------------------------------------------------------- DB


def db_cells(db: Path, spec_path: Path) -> list[dict[str, Any]]:
    """Read one SQLite DB and return one cell per run, keyed by plan factors."""
    spec = spec_module.load(spec_path)
    plans = {plan.run_id: plan for plan in compiler.compile_spec(spec)}
    cells: list[dict[str, Any]] = []
    with ResultStore(db) as store:
        for row in store.runs():
            plan = plans.get(row["run_id"])
            if plan is None:
                continue
            by_metric: dict[str, list[float]] = defaultdict(list)
            errors = 0
            for metric in store.metrics(run_id=row["run_id"]):
                if metric["metric"] == "error":
                    errors += 1
                    continue
                if metric["value"] is not None:
                    by_metric[metric["metric"]].append(float(metric["value"]))
            cells.append(
                {
                    "run_id": row["run_id"],
                    "factors": json.loads(row["factors_json"] or "{}"),
                    "config_hash": row["config_hash"],
                    "status": row["status"],
                    "n": len(by_metric.get("evidence_recall", [])),
                    "errors": errors,
                    "evidence_recall": _mean(by_metric.get("evidence_recall", [])),
                    "ndcg": _mean(by_metric.get("ndcg", [])),
                    "answer_f1": _mean(by_metric.get("answer_f1", [])),
                    "context_precision": _mean(by_metric.get("context_precision", [])),
                    "candidates": _mean(by_metric.get("candidates", [])),
                    "graph_nodes": _mean(by_metric.get("graph_nodes", [])),
                    "graph_edges": _mean(by_metric.get("graph_edges", [])),
                    "latency_mean_ms": _mean(by_metric.get("latency_ms", [])),
                    "latency_p95_ms": _p95(by_metric.get("latency_ms", [])),
                    "field_completeness": _mean(by_metric.get("field_completeness", [])),
                    "unique_gold_hits": _mean(by_metric.get("unique_gold_hits", [])),
                    "unique_gold_hits_total": int(sum(by_metric.get("unique_gold_hits", []))),
                    "unique_candidates": _mean(by_metric.get("unique_candidates", [])),
                    "unique_candidates_total": int(sum(by_metric.get("unique_candidates", []))),
                    "config": {
                        "schema": plan.effective_config.get("schema", {}).get("impl"),
                        "graph_repr": plan.effective_config.get("graph", {}).get("repr", {}).get("impl"),
                        "graph_retrieval": plan.effective_config.get("graph", {}).get("retrieval", {}).get("impl"),
                        "fusion": plan.effective_config.get("fusion", {}).get("impl"),
                        "channels": plan.effective_config.get("retrieval", {}).get("channels"),
                    },
                }
            )
    return cells


def _cell_by(cells: Sequence[Mapping[str, Any]], **wanted: Any) -> Mapping[str, Any]:
    for cell in cells:
        if all(cell.get("config", {}).get(key) == value for key, value in wanted.items()):
            return cell
    raise KeyError(f"no cell with {wanted}; have {[cell['config'] for cell in cells]}")


# ------------------------------------------------------------------- pipeline diagnostics


def diagnose(db: Path, spec_path: Path) -> dict[str, Any]:
    """Re-run each cell's pipeline to expose channel candidates and survival.

    The executor only stores final turns; this is the only way to recover the
    per-channel candidate sets and graph-novel candidates that the M stage
    truncates.  It is deterministic and does not call a model.
    """
    spec = spec_module.load(spec_path)
    plans = compiler.compile_spec(spec)
    questions = runner.load_questions(spec)
    records: list[dict[str, Any]] = []
    cells: dict[str, dict[str, Any]] = {}
    for plan in plans:
        contexts: dict[str, Any] = {}
        pipelines: dict[str, E2EPipeline] = {}
        cell = {
            "run_id": plan.run_id,
            "factors": plan.factors,
            "questions": len(questions),
            "intents": Counter(),
            "questions_with_graph": 0,
            "channel_recall_sum": defaultdict(float),
            "channel_gold_hits": Counter(),
            "channel_unique_gold": Counter(),
            "channel_unique_questions": Counter(),
            "_unique_question_seen": defaultdict(set),
            "channel_candidates": Counter(),
            "graph_novel_candidates": 0,
            "graph_novel_gold_candidates": 0,
            "graph_novel_in_final": 0,
            "graph_novel_gold_in_final": 0,
            "graph_sourced_final_units": 0,
            "final_units": 0,
            "final_channel_mix": Counter(),
            "final_recall_sum": 0.0,
            "channel_recall_questions": Counter(),
        }
        for question in questions:
            sample = question.sample_id
            if sample not in contexts:
                contexts[sample] = build_context(plan, sample, offline=True)
                pipelines[sample] = E2EPipeline(contexts[sample])
            ctx = contexts[sample]
            pipeline = pipelines[sample]
            gold = set(_gold(question))
            result = pipeline.run(question.qa["question"], k=K, gold_turns=sorted(gold))
            retrieval = result.retrieval
            intent = retrieval.frame.intent
            cell["intents"][intent] += 1
            channels: dict[str, set[str]] = {}
            channel_ids: dict[str, set[str]] = {}
            for name, candidates in retrieval.by_channel.items():
                channel_ids[name] = {candidate.memory_id for candidate in candidates}
                channels[name] = merge.recalled_turns(ctx.store, candidates)
                cell["channel_candidates"][name] += len(candidates)
                if gold:
                    cell["channel_recall_sum"][name] += len(gold & channels[name]) / len(gold)
                    cell["channel_recall_questions"][name] += 1
                if gold & channels[name]:
                    cell["channel_gold_hits"][name] += len(gold & channels[name])
            if "graph_khop" in channel_ids:
                cell["questions_with_graph"] += 1
            # A gold turn is "unique" to a channel when no other built channel
            # returned any candidate carrying it.
            if gold:
                owners: dict[str, list[str]] = defaultdict(list)
                for name, turns in channels.items():
                    for turn in gold & turns:
                        owners[turn].append(name)
                for turn, names in owners.items():
                    if len(names) == 1:
                        cell["channel_unique_gold"][names[0]] += 1
                        cell["_unique_question_seen"][names[0]].add(question.qid)
            # Graph-novel: a graph candidate memory id absent from every
            # non-graph channel; count how many reach the final context.
            graph_ids = channel_ids.get("graph_khop", set())
            other_ids: set[str] = set()
            for name, ids in channel_ids.items():
                if name != "graph_khop":
                    other_ids |= ids
            novel_ids = graph_ids - other_ids
            cell["graph_novel_candidates"] += len(novel_ids)
            for memory_id in novel_ids:
                unit = ctx.store.get(memory_id)
                if unit is not None and gold & merge.unit_turns(unit):
                    cell["graph_novel_gold_candidates"] += 1
            final_ids = {unit.memory_id for unit in result.merge.units}
            provenance = {candidate.memory_id: candidate.provenance.get("channels", [candidate.channel])
                          for candidate in result.merge.candidates}
            for memory_id in final_ids:
                for name in set(provenance.get(memory_id, [])):
                    cell["final_channel_mix"][name] += 1
            cell["final_units"] += len(result.merge.units)
            cell["graph_novel_in_final"] += len(novel_ids & final_ids)
            for memory_id in novel_ids & final_ids:
                unit = ctx.store.get(memory_id)
                if unit is not None and gold & merge.unit_turns(unit):
                    cell["graph_novel_gold_in_final"] += 1
            cell["graph_sourced_final_units"] += sum(
                1 for memory_id in final_ids if memory_id in graph_ids
            )
            if gold:
                final_turns: set[str] = set()
                for unit in result.merge.units:
                    final_turns |= merge.unit_turns(unit)
                cell["final_recall_sum"] += len(gold & final_turns) / len(gold)
            records.append(
                {
                    "run_id": plan.run_id,
                    "qid": question.qid,
                    "intent": intent,
                    "channels": {name: sorted(ids) for name, ids in channel_ids.items()},
                }
            )
        cell["intents"] = dict(cell["intents"])
        cell["channel_unique_questions"] = {
            name: len(qids) for name, qids in cell["_unique_question_seen"].items()
        }
        cell.pop("_unique_question_seen", None)
        for key in (
            "channel_recall_sum",
            "channel_gold_hits",
            "channel_unique_gold",
            "channel_unique_questions",
            "channel_candidates",
            "channel_recall_questions",
            "final_channel_mix",
        ):
            cell[key] = dict(cell[key])
        cell["channel_recall"] = {
            name: _round(cell["channel_recall_sum"].get(name, 0.0) / max(1, cell["channel_recall_questions"].get(name, 0)))
            for name in cell["channel_recall_sum"]
        }
        cell["final_recall_check"] = _round(cell["final_recall_sum"] / max(1, len(questions)))
        cell["channel_recall_sum"] = {name: _round(value) for name, value in cell["channel_recall_sum"].items()}
        cells[plan.run_id] = cell
    return {"cells": cells, "records": records, "questions": len(questions)}


# ------------------------------------------------------------------------- P1 single channel


def run_single_channels() -> dict[str, Any]:
    spec = spec_module.load(P1_SPEC)
    plans = compiler.compile_spec(spec)
    questions = runner.load_questions(spec)
    if len(questions) != 61:
        raise RuntimeError(f"expected 61 multi-hop questions, got {len(questions)}")
    # All four plans share the same underlying config except retrieval.channels;
    # one context per conversation is enough and keeps the comparison paired.
    contexts: dict[str, Any] = {}
    channel_of: dict[str, str] = {}
    for plan in plans:
        channel = (plan.factors.get("retrieval.channels") or [None])[0]
        channel_of[plan.run_id] = str(channel)
    if len(set(channel_of.values())) != 4:
        raise RuntimeError(f"expected four distinct single-channel plans, got {channel_of}")
    started = time.perf_counter()
    # Compute all four channels for every question before writing metrics so a
    # per-question "unique to this channel" count is available.
    per_run: dict[str, dict[str, dict[str, Any]]] = {run_id: {} for run_id in channel_of}
    for plan in plans:
        channel = channel_of[plan.run_id]
        analyzer = RuleAnalyzer()
        for question in questions:
            sample = question.sample_id
            if sample not in contexts:
                contexts[sample] = build_context(plans[0], sample, offline=True)
            ctx = contexts[sample]
            frame = analyzer.analyze(question.qa["question"], ctx)
            node = PlanNode(node_id="n1", query=frame.query, channel=channel, k=K)
            begun = time.perf_counter()
            candidates = registry.build("retrieval.channel", channel).retrieve(frame, node, K, ctx)
            latency = round((time.perf_counter() - begun) * 1000, 3)
            gold = set(_gold(question))
            turns = merge.recalled_turns(ctx.store, candidates)
            per_run[plan.run_id][question.qid] = {
                "candidates": candidates,
                "turns": turns,
                "latency_ms": latency,
                "recall": (len(gold & turns) / len(gold)) if gold else None,
                "ndcg": merge.ndcg_at_k(ctx.store, candidates, sorted(gold)) if gold else None,
                "context_precision": merge.context_precision(ctx.store, candidates, sorted(gold)) if gold else None,
            }
    with ResultStore(P1_DB) as store:
        for plan in plans:
            store.upsert_run(plan, status="running")
            channel = channel_of[plan.run_id]
            for question in questions:
                item = per_run[plan.run_id][question.qid]
                other_turns: set[str] = set()
                other_ids: set[str] = set()
                for other_run, other_channel in channel_of.items():
                    if other_run == plan.run_id:
                        continue
                    other = per_run[other_run][question.qid]
                    other_turns |= other["turns"]
                    other_ids |= {candidate.memory_id for candidate in other["candidates"]}
                unique_turns = item["turns"] - other_turns
                unique_ids = {
                    candidate.memory_id for candidate in item["candidates"]
                } - other_ids
                gold = set(_gold(question))
                metrics = {
                    "evidence_recall": item["recall"],
                    "ndcg": item["ndcg"],
                    "context_precision": item["context_precision"],
                    "candidates": len(item["candidates"]),
                    "latency_ms": item["latency_ms"],
                    "unique_gold_hits": len(gold & unique_turns),
                    "unique_candidates": len(unique_ids),
                }
                store.add_metrics(plan.run_id, question.qid, metrics)
            store.set_status(plan.run_id, "complete")
    return {
        "db": str(P1_DB.relative_to(ROOT)),
        "elapsed_s": round(time.perf_counter() - started, 2),
        "runs": len(plans),
        "questions_per_run": len(questions),
    }


# ------------------------------------------------------------------------- archive helpers


def _metric_map(db: Path, run_id: str, metric: str) -> dict[str, float]:
    with ResultStore(db) as store:
        rows = store.metrics(run_id=run_id, metric=metric)
    return {row["qid"]: float(row["value"]) for row in rows if row["value"] is not None}


def paired(db: Path, run_a: str, run_b: str, metrics: Sequence[str]) -> dict[str, Any]:
    """Per-question paired deltas (b - a) for one pair of runs."""
    out: dict[str, Any] = {}
    for metric in metrics:
        left = _metric_map(db, run_a, metric)
        right = _metric_map(db, run_b, metric)
        qids = sorted(set(left) & set(right))
        deltas = [right[qid] - left[qid] for qid in qids]
        if not deltas:
            out[metric] = None
            continue
        out[metric] = {
            "n": len(deltas),
            "mean_delta": _round(statistics.mean(deltas)),
            "median_delta": _round(statistics.median(deltas)),
            "improved": sum(1 for value in deltas if value > 1e-12),
            "worsened": sum(1 for value in deltas if value < -1e-12),
            "unchanged": sum(1 for value in deltas if abs(value) <= 1e-12),
        }
    return out


def interaction(db: Path, runs: Mapping[str, str], metrics: Sequence[str]) -> dict[str, Any]:
    """Difference-in-differences for a 2x2.

    ``runs`` keys are ``a0_b0``, ``a1_b0``, ``a0_b1``, ``a1_b1`` where ``a`` is
    the row factor (schema/graph route) and ``b`` the column factor (graph/fusion).
    """
    out: dict[str, Any] = {}
    for metric in metrics:
        values = {key: _metric_map(db, run_id, metric) for key, run_id in runs.items()}
        qids = set.intersection(*(set(item) for item in values.values()))
        # Effect of the row factor under b=1 minus under b=0.  For a balanced
        # 2x2 this equals y11-y10-y01+y00, the usual interaction contrast.
        dod = [((values["a1_b1"][qid] - values["a1_b0"][qid])
                - (values["a0_b1"][qid] - values["a0_b0"][qid])) for qid in sorted(qids)]
        if not dod:
            out[metric] = None
            continue
        out[metric] = {
            "n": len(dod),
            "difference_in_differences": _round(statistics.mean(dod)),
            "median_dod": _round(statistics.median(dod)),
            "positive": sum(1 for value in dod if value > 1e-12),
            "negative": sum(1 for value in dod if value < -1e-12),
            "zero": sum(1 for value in dod if abs(value) <= 1e-12),
            "cell_means": {
                key: _round(statistics.mean(values[key][qid] for qid in qids))
                for key in ("a0_b0", "a1_b0", "a0_b1", "a1_b1")
            },
        }
    return out


def _pick(cells: Sequence[Mapping[str, Any]], **wanted: Any) -> Mapping[str, Any]:
    for cell in cells:
        config = cell.get("config") or {}
        if all(config.get(key) == value for key, value in wanted.items()):
            return cell
    raise KeyError(f"no cell with {wanted}: {[cell.get('config') for cell in cells]}")


def p1_channel_summary(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for cell in cells:
        channel = (cell.get("factors") or {}).get("retrieval.channels") or []
        rows.append(
            {
                "channel": channel[0] if isinstance(channel, list) and channel else None,
                "run_id": cell["run_id"],
                "n": cell["n"],
                "evidence_recall": cell["evidence_recall"],
                "ndcg": cell["ndcg"],
                "context_precision": cell["context_precision"],
                "candidates": cell["candidates"],
                "unique_gold_hits_total": cell["unique_gold_hits_total"],
                "unique_candidates_total": cell["unique_candidates_total"],
                "latency_mean_ms": cell["latency_mean_ms"],
            }
        )
    return rows


def p1_bm25_temporal_identical(cells: Sequence[Mapping[str, Any]]) -> int:
    bm25 = _pick(cells, channels=["bm25"])
    temporal = _pick(cells, channels=["temporal"])
    left = _metric_map(P1_DB, bm25["run_id"], "evidence_recall")
    right = _metric_map(P1_DB, temporal["run_id"], "evidence_recall")
    return sum(1 for qid in set(left) & set(right) if abs(left[qid] - right[qid]) <= 1e-12)


def build_archive() -> dict[str, Any]:
    p01 = db_cells(RUNS / "event_sparse.sqlite", ROOT / "configs" / "experiments" / "g2-e1-s2-event-sparse.json")
    p02 = db_cells(RUNS / "wr.sqlite", ROOT / "configs" / "experiments" / "g2-e2-wr.json")
    p03 = db_cells(RUNS / "m1-route.sqlite", ROOT / "configs" / "experiments" / "g2-e1-m1-graph-route.json")
    p1 = db_cells(P1_DB, P1_SPEC) if P1_DB.exists() else []
    diag01 = diagnose(RUNS / "event_sparse.sqlite", ROOT / "configs" / "experiments" / "g2-e1-s2-event-sparse.json")
    diag02 = diagnose(RUNS / "wr.sqlite", ROOT / "configs" / "experiments" / "g2-e2-wr.json")
    diag03 = diagnose(RUNS / "m1-route.sqlite", ROOT / "configs" / "experiments" / "g2-e1-m1-graph-route.json")
    # attach diagnostics
    for cells, diag in ((p01, diag01), (p02, diag02), (p03, diag03)):
        for cell in cells:
            detail = diag["cells"].get(cell["run_id"], {})
            cell["routing"] = detail.get("intents")
            cell["questions_with_graph"] = detail.get("questions_with_graph")
            cell["channel_recall"] = detail.get("channel_recall")
            cell["channel_unique_gold"] = detail.get("channel_unique_gold")
            cell["channel_unique_questions"] = detail.get("channel_unique_questions")
            cell["graph_novel_candidates"] = detail.get("graph_novel_candidates")
            cell["graph_novel_gold_candidates"] = detail.get("graph_novel_gold_candidates")
            cell["graph_novel_in_final"] = detail.get("graph_novel_in_final")
            cell["graph_novel_gold_in_final"] = detail.get("graph_novel_gold_in_final")
            cell["graph_sourced_final_units"] = detail.get("graph_sourced_final_units")
            cell["final_units"] = detail.get("final_units")
            cell["final_channel_mix"] = detail.get("final_channel_mix")

    archive: dict[str, Any] = {
        "schema": "memlab/graph-completion@1",
        "experiment": "G2 graph completion",
        "generated_at": _now(),
        "protocol": {
            "offline": True,
            "executor": "e2e",
            "llm": "offline-extractive",
            "embedding": "offline-hash",
            "subset": "LoCoMo category=1 (multi-hop)",
            "samples": ["conv-26", "conv-30", "conv-43", "conv-44"],
            "questions_per_config": 61,
            "k": K,
            "cells": len(p01) + len(p02) + len(p03) + len(p1),
            "note": "A-level offline only. A online 27B numbers are a pre-wiring harness and are not comparable.",
        },
        "p0_1_event_sparse": {
            "db": "runs/graph-completion/event_sparse.sqlite",
            "spec": "configs/experiments/g2-e1-s2-event-sparse.json",
            "cells": p01,
        },
        "p0_2_wr": {
            "db": "runs/graph-completion/wr.sqlite",
            "spec": "configs/experiments/g2-e2-wr.json",
            "cells": p02,
        },
        "p0_3_m1_route": {
            "db": "runs/graph-completion/m1-route.sqlite",
            "spec": "configs/experiments/g2-e1-m1-graph-route.json",
            "cells": p03,
        },
        "p1_r2_single_channel": {
            "db": "runs/graph-completion/single-channel.sqlite",
            "spec": "configs/experiments/g2-e1-r2-single-channel.json",
            "cells": p1,
            "channel_summary": p1_channel_summary(p1),
            "bm25_temporal_identical_questions": p1_bm25_temporal_identical(p1),
        },
        "deviations": [
            "retrieval.channels is validated but never consumed by RuleRouterPlanner; P0-3 therefore expresses the graph route with graph.retrieval.impl=vector_only/entity_subgraph (bm25+dense vs bm25+graph_khop), not as an added third channel.",
            "When the graph is on, the router returns bm25+graph_khop and drops dense; the requested bm25+dense+graph_khop union does not exist without changing retrieve.py, which this session was told not to touch.",
            "P1 single channels are executed by eval/graph_completion_analyze.py, not by the S5 runner, because no planner can select dense/graph/temporal alone from retrieval.channels.",
            "legacy_flat in P0-2 is closed with temporal.model=record_time because reference bi-temporal requires meta_schema; the W effect therefore carries the schema's temporal projection with it.",
        ],
        "limitations": [
            "Offline hashing embeddings are not semantic; vector_only is a weak dense baseline, not bge-m3.",
            "Only 4 development conversations and 61 category-1 questions per configuration; single seed; no significance claim.",
            "The rule analyzer routes only 8/61 category-1 questions to the graph channel; most final cells cannot exercise the graph.",
            "Under R0 query_adaptive fusion (R3/S2/E2), graph-novel candidates enter the final context 0 times. Under plain RRF they can enter (44 units), but only 2 are gold and final Recall moves +0.0049 with 1 question improved and 1 worsened, so the final metric stays effectively insensitive to graph representation/retrieval.",
            "answer_f1 is an extractive string-overlap baseline, not an LLM answer; P2 rerank is blocked on hardware and no filter is used as a rerank substitute.",
        ],
    }
    # ---------------------------------------------------------- paired / interaction
    p01_vector = _pick(p01, graph_retrieval="vector_only")
    p01_graph = _pick(p01, graph_retrieval="entity_subgraph")
    archive["p0_1_event_sparse"]["paired_vs_vector_only"] = paired(
        RUNS / "event_sparse.sqlite", p01_vector["run_id"], p01_graph["run_id"],
        ("evidence_recall", "ndcg", "answer_f1"),
    )
    archive["p0_1_event_sparse"]["graph_unique_hits"] = {
        "graph_novel_candidates": p01_graph["graph_novel_candidates"],
        "graph_novel_gold_candidates": p01_graph["graph_novel_gold_candidates"],
        "graph_novel_in_final": p01_graph["graph_novel_in_final"],
        "graph_novel_gold_in_final": p01_graph["graph_novel_gold_in_final"],
    }

    p02_runs = {
        "a0_b0": _pick(p02, schema="legacy_flat", graph_retrieval="vector_only")["run_id"],
        "a1_b0": _pick(p02, schema="meta_schema", graph_retrieval="vector_only")["run_id"],
        "a0_b1": _pick(p02, schema="legacy_flat", graph_retrieval="entity_subgraph")["run_id"],
        "a1_b1": _pick(p02, schema="meta_schema", graph_retrieval="entity_subgraph")["run_id"],
    }
    archive["p0_2_wr"]["interaction"] = interaction(
        RUNS / "wr.sqlite", p02_runs, ("evidence_recall", "ndcg")
    )
    archive["p0_2_wr"]["orientation"] = "DoD = graph gain under meta_schema minus graph gain under legacy_flat; positive means structured writes make the graph more effective"
    archive["p0_2_wr"]["graph_on_minus_off"] = {
        "legacy_flat": paired(RUNS / "wr.sqlite", p02_runs["a0_b0"], p02_runs["a0_b1"],
                              ("evidence_recall", "ndcg")),
        "meta_schema": paired(RUNS / "wr.sqlite", p02_runs["a1_b0"], p02_runs["a1_b1"],
                              ("evidence_recall", "ndcg")),
    }
    archive["p0_2_wr"]["meta_minus_legacy"] = {
        "vector_only": paired(RUNS / "wr.sqlite", p02_runs["a0_b0"], p02_runs["a1_b0"],
                              ("evidence_recall", "ndcg")),
        "entity_subgraph": paired(RUNS / "wr.sqlite", p02_runs["a0_b1"], p02_runs["a1_b1"],
                                  ("evidence_recall", "ndcg")),
    }

    p03_runs = {
        "a0_b0": _pick(p03, graph_retrieval="vector_only", fusion="rrf")["run_id"],
        "a1_b0": _pick(p03, graph_retrieval="entity_subgraph", fusion="rrf")["run_id"],
        "a0_b1": _pick(p03, graph_retrieval="vector_only", fusion="weighted_rrf")["run_id"],
        "a1_b1": _pick(p03, graph_retrieval="entity_subgraph", fusion="weighted_rrf")["run_id"],
    }
    archive["p0_3_m1_route"]["interaction"] = interaction(
        RUNS / "m1-route.sqlite", p03_runs, ("evidence_recall", "ndcg")
    )
    archive["p0_3_m1_route"]["orientation"] = "DoD = graph gain under weighted_rrf minus graph gain under rrf; positive means the fusion method changes how much the graph route adds"
    archive["p0_3_m1_route"]["graph_on_minus_off"] = {
        "rrf": paired(RUNS / "m1-route.sqlite", p03_runs["a0_b0"], p03_runs["a1_b0"],
                      ("evidence_recall", "ndcg")),
        "weighted_rrf": paired(RUNS / "m1-route.sqlite", p03_runs["a0_b1"], p03_runs["a1_b1"],
                               ("evidence_recall", "ndcg")),
    }
    archive["p0_3_m1_route"]["weighted_rrf_minus_rrf"] = {
        "vector_only": paired(RUNS / "m1-route.sqlite", p03_runs["a0_b0"], p03_runs["a0_b1"],
                              ("evidence_recall", "ndcg")),
        "entity_subgraph": paired(RUNS / "m1-route.sqlite", p03_runs["a1_b0"], p03_runs["a1_b1"],
                                  ("evidence_recall", "ndcg")),
    }
    archive["p0_3_m1_route"]["route_arm_unique_hits"] = {
        "definition": "candidate-level: gold memory units returned by graph_khop but by no non-graph channel; final counts units that survive into the merged context. Gold turns unique to one channel are in each cell's channel_unique_gold.",
        "rrf": {
            "graph_novel_candidates": _pick(p03, graph_retrieval="entity_subgraph", fusion="rrf")["graph_novel_candidates"],
            "graph_novel_gold_candidates": _pick(p03, graph_retrieval="entity_subgraph", fusion="rrf")["graph_novel_gold_candidates"],
            "graph_novel_in_final": _pick(p03, graph_retrieval="entity_subgraph", fusion="rrf")["graph_novel_in_final"],
            "graph_novel_gold_in_final": _pick(p03, graph_retrieval="entity_subgraph", fusion="rrf")["graph_novel_gold_in_final"],
        },
        "weighted_rrf": {
            "graph_novel_candidates": _pick(p03, graph_retrieval="entity_subgraph", fusion="weighted_rrf")["graph_novel_candidates"],
            "graph_novel_gold_candidates": _pick(p03, graph_retrieval="entity_subgraph", fusion="weighted_rrf")["graph_novel_gold_candidates"],
            "graph_novel_in_final": _pick(p03, graph_retrieval="entity_subgraph", fusion="weighted_rrf")["graph_novel_in_final"],
            "graph_novel_gold_in_final": _pick(p03, graph_retrieval="entity_subgraph", fusion="weighted_rrf")["graph_novel_gold_in_final"],
        },
    }

    archive["completeness"] = [
        {"id": "E1-S2a", "experiment": "图表示 state_slot/entity_triple/three_layer", "status": "done",
         "evidence": "R3 13 cells: final Recall 0.2372 for every graph repr; NDCG 0.2315-0.2324; graph-novel 0 survive."},
        {"id": "E1-S2b", "experiment": "图表示 event_sparse", "status": "done",
         "evidence": "G2 2 cells: vector_only 0.2257 / entity_subgraph 0.2372; same +0.0115 as the other reprs; event_sparse graph 791 nodes / 246 edges."},
        {"id": "E1-R3", "experiment": "图检索 impl (slot_expand/entity_subgraph/dual_channel/ppr)", "status": "done",
         "evidence": "R3 13 cells: all final Recall 0.2372; PPR NDCG +0.0003..+0.0066, p95 1.6-2x; graph-novel 34-91, 0 survive."},
        {"id": "E1-R2", "experiment": "单通道 bm25/dense/graph/temporal", "status": "partial",
         "evidence": "G2 4 single-channel cells; bm25 0.3560, temporal 0.3560 (identical fallback), graph 0.1854, dense 0.0367; unique gold bm25 0 / dense 3 / graph 4 / temporal 0."},
        {"id": "E1-M1", "experiment": "路线臂 (graph off/on) x fusion (rrf/weighted_rrf)", "status": "partial",
         "evidence": "G2 4 cells; graph adds +0.0049 recall under RRF but weighted RRF collapses to 0.0279/0.0795; under RRF 44 graph-novel units enter context, 2 of them gold."},
        {"id": "E2-WR", "experiment": "W x R: schema x graph", "status": "partial",
         "evidence": "G2 4 cells; graph gain +0.0082 (legacy) vs +0.0115 (meta), DoD +0.0033 recall; field completeness 0 vs 1."},
        {"id": "E2-SM", "experiment": "S x M: graph repr x rerank", "status": "blocked_on_hardware",
         "evidence": "No GPU / sentence-transformers; cross_encoder falls back. Not run; no filter used as rerank."},
        {"id": "E3", "experiment": "图组合 (state_slot vs three_layer in 2^(5-1))", "status": "done",
         "evidence": "E3 offline 240 q: graph main effect 0.0 on recall and NDCG; graph+rerank interaction 0.0."},
    ]
    archive["p2_sxm"] = {
        "status": "blocked_on_hardware",
        "reason": "cross_encoder reranker needs sentence-transformers / GPU; no model weights available offline.",
        "guard": "No threshold filter or other stage is reported as a rerank substitute. The design is recorded but not run.",
        "requested_design": "graph.repr.impl x rerank.impl (none / cross_encoder), fixed retrieval and fusion",
        "next": "Run when a cross-encoder is installed; keep the same 61-question paired subset.",
    }
    archive["headline"] = {
        "graph_novel_reaches_context_under_default_R0_fusion": False,
        "graph_novel_ever_reaches_context": True,
        "graph_novel_gold_reaches_context_under_plain_RRF": 2,
        "final_recall_flat_across_graph_impl_and_repr": True,
        "route_limiter": "rule analyzer routes 8/61 category-1 questions to graph",
        "fusion_limiter": "under R0 query_adaptive fusion, graph-novel candidates are cut by fusion/filter/top-15; plain RRF admits 44 but only 2 are gold",
        "W_effect": "meta_schema +0.0348 recall vs legacy_flat under vector_only; +0.0381 under graph",
    }
    return archive


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("p1", "archive", "all"), nargs="?", default="all")
    args = parser.parse_args(argv)
    if args.command in ("p1", "all"):
        if P1_DB.exists():
            P1_DB.unlink()
        print(json.dumps(run_single_channels(), ensure_ascii=False, indent=2))
    if args.command in ("archive", "all"):
        archive = build_archive()
        ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVE.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"archive": str(ARCHIVE.relative_to(ROOT)), "cells": archive["protocol"]["cells"]},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
