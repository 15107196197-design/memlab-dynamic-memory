"""E2-2 retrieval oracle: gold evidence -> M -> U.

This is deliberately narrow: only retrieval is replaced by an oracle.  The answerer
and merge pipeline are the frozen R0 config, so the gap is "system retrieval vs
oracle retrieval", not an oracle answer.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from memlab import config as lab_config
from memlab import model
from memlab.contracts import Candidate, Plan, PlanNode
from memlab.e2e import E2EPipeline
from memlab.experiments import compiler, executor, store as store_module
from memlab.experiments.runner import Question, evaluate_result
from memlab.registry import build as build_impl
from memlab.retrieve import AXIS_ANALYZER, RetrievalResult
from memlab.trace import Trace
from memwb import dataset, evaluation

SAMPLES = ["conv-26", "conv-30", "conv-43", "conv-44"]


class OracleRunner:
    def __init__(self, gold_turns):
        self.gold_turns = set(gold_turns)

    def run(self, query: str, ctx, k: int | None = None):
        frame = build_impl(AXIS_ANALYZER, "rule").analyze(query, ctx)
        plan = Plan(nodes=[PlanNode(node_id="oracle", query=query, channel="oracle")],
                    parallel_groups=[["oracle"]], rationale="gold evidence injected")
        candidates = []
        for unit in ctx.store.units:
            turns = set()
            if unit.kind == "turn" and unit.structured.get("turn"):
                turns.add(str(unit.structured["turn"]))
            turns |= {span.turn_id for span in unit.evidence}
            if turns & self.gold_turns:
                candidates.append(Candidate(memory_id=unit.memory_id, channel="oracle",
                                            rank=len(candidates) + 1, raw_score=1.0, score=1.0,
                                            stage_scores={"oracle": 1.0},
                                            provenance={"oracle": True}))
        trace = Trace()
        trace.add("retrieve", "oracle", f"{len(candidates)} gold units injected")
        return RetrievalResult(frame=frame, plan=plan, candidates=candidates,
                               trace=trace.to_list(), k=k or 15,
                               by_channel={"oracle": candidates})


def select_questions(sample_id: str, limit: int, seed: int) -> list[Question]:
    sample = dataset.store().get(sample_id)
    return [Question(sample_id, index, qa)
            for index, qa in evaluation.stratified(sample.get("qa", []), limit)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--seeds", type=int, nargs="+", default=[13])
    parser.add_argument("--samples", nargs="+", default=SAMPLES)
    parser.add_argument("--db", default=str(ROOT / "runs" / "e2" / "oracle.sqlite"))
    parser.add_argument("--out", default=str(ROOT / "eval" / "archive" / "e2-oracle-retrieval.json"))
    args = parser.parse_args(argv)
    base = lab_config.RunConfig.load(ROOT / "configs" / "reference-r0.json").to_dict()
    base.setdefault("environment", {}).setdefault("llm", {})["context"] = 8192
    config = lab_config.RunConfig.from_dict(base)
    digest = lab_config.digest(base)
    plan = compiler.RunPlan(run_id="e2-oracle-retrieval", spec_id="E2-2",
                            design="oracle_retrieval", config=base, requested_config=base,
                            effective_config=base, config_hash=digest,
                            environment=base.get("environment"), dataset={"samples": args.samples},
                            factors={"oracle": "retrieval"})
    records = []
    started = time.time()
    db = Path(args.db); db.parent.mkdir(parents=True, exist_ok=True)
    with store_module.ResultStore(db) as store:
        store.upsert_run(plan, status="running")
        for sample_id in args.samples:
            ctx = executor.build_context(plan, sample_id, offline=False)
            questions = select_questions(sample_id, args.questions, args.seeds[0])
            for q in questions:
                gold = evaluation.evidence_turns(q.qa)
                result = E2EPipeline(ctx, runner=OracleRunner(gold)).run(
                    q.qa["question"], k=15, gold_turns=gold)
                metrics = evaluate_result({
                    "answer": result.answer.answer,
                    "retrieved_turns": sorted({t for u in result.merge.units for t in _unit_turns(u)}),
                    "tokens": result.tokens,
                    "latency_ms": result.latency_ms,
                }, q)
                metrics["oracle_units"] = len(result.merge.candidates)
                store.add_metrics(plan.run_id, q.qid, metrics)
                records.append({"qid": q.qid, "sample": sample_id, **metrics})
                print(json.dumps({"qid": q.qid, "f1": metrics.get("answer_f1"),
                                  "tokens": metrics.get("tokens")}), flush=True)
        store.set_status(plan.run_id, "complete")
    summary = {
        "schema": "memlab/e2-oracle@1",
        "experiment_id": "e2-oracle-retrieval",
        "samples": args.samples, "questions": len(records), "seed": args.seeds[0],
        "metrics": {
            "answer_f1": round(statistics.mean([r["answer_f1"] for r in records if r.get("answer_f1") is not None]), 4)
            if any(r.get("answer_f1") is not None for r in records) else None,
            "evidence_recall": round(statistics.mean([r["evidence_recall"] for r in records if r.get("evidence_recall") is not None]), 4)
            if any(r.get("evidence_recall") is not None for r in records) else None,
            "tokens": round(statistics.mean([r["tokens"] for r in records if r.get("tokens") is not None]), 2)
            if any(r.get("tokens") is not None for r in records) else None,
            "latency_ms": round(statistics.mean([r["latency_ms"] for r in records if r.get("latency_ms") is not None]), 2)
            if any(r.get("latency_ms") is not None for r in records) else None,
        },
        "elapsed_seconds": round(time.time() - started, 1),
        "run_id": plan.run_id,
    }
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _unit_turns(unit):
    turns = set()
    if unit.kind == "turn" and unit.structured.get("turn"):
        turns.add(str(unit.structured["turn"]))
    turns |= {span.turn_id for span in unit.evidence}
    return turns


if __name__ == "__main__":
    raise SystemExit(main())
