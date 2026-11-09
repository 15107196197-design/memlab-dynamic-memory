"""S4 tests: M fusion/rerank/post waterfall, U state/answer, K maintenance, end-to-end."""
import json
import math
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from memlab import cache, config as lab_config, maintenance, merge, runtime, store as store_module, use
from memlab.contracts import Candidate, Interval, MemoryUnit, Plan, QueryFrame, Span
from memlab.e2e import E2EPipeline
from memlab.ingest import build_store
from memlab.retrieve import RetrievalResult, RetrievalRunner
from memwb import dataset, evaluation, memory

REFERENCE_B0 = lab_config.ROOT / "configs" / "reference-b0.json"

_TMP: tempfile.TemporaryDirectory | None = None
_FIXTURE: dict | None = None


def setUpModule():
    global _TMP
    _TMP = tempfile.TemporaryDirectory()


def tearDownModule():
    if _TMP is not None:
        _TMP.cleanup()


class FakeEmbedding:
    dimensions = 32

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for index, character in enumerate(str(text)):
                vector[(index * 31 + ord(character)) % self.dimensions] += 1.0
            if not any(vector):
                vector[0] = 1.0
            vectors.append(vector)
        return vectors

    def fingerprint(self):
        return "sha256:" + "f" * 64


class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def generate(self, prompt, json_mode=False):
        self.calls.append(prompt)
        if self.error:
            raise self.error
        if self.reply is not None:
            return self.reply(prompt)
        if "temporal memory analyst" in prompt:
            return {"memories": []}
        citations = re.findall(r"\bD\d+:\d+\b", prompt)[:1]
        return {"answer": "the retrieved evidence supports this", "citations": citations, "refused": False}


def runtime_fixture():
    global _FIXTURE
    if _FIXTURE is None:
        data = lab_config.RunConfig.load(REFERENCE_B0).to_dict()
        data["planner"] = {"impl": "rule_router", "params": {}}
        config = lab_config.RunConfig.from_dict(data)
        sample = dataset.store().get("conv-26")
        turns, facts = memory.build(sample)
        llm = FakeLLM()
        rt = runtime.Runtime(config, llm=llm, embedding=FakeEmbedding(),
                             cache=cache.ArtifactCache(Path(_TMP.name) / "artifacts"))
        ingested = build_store(sample, rt)
        rt.attach_store(ingested.store)
        _FIXTURE = {
            "config": config, "sample": sample, "turns": turns, "facts": facts,
            "llm": llm, "runtime": rt, "ingested": ingested, "store": ingested.store,
            "questions": [question for _, question in evaluation.stratified(sample.get("qa", []), 10)],
        }
    return _FIXTURE


def unit(memory_id="a", *, text=None, kind="fact", state="ACTIVE", entity="Caroline",
         attribute="job", value="teacher", turn="D1:1", start="2023-05-01T10:00",
         end=None, event="2023-05-01"):
    event_start = merge_date(event)
    ingest_start = merge_date(start)
    valid_end = merge_date(end)
    structured = {"entity": entity, "attribute": attribute, "value": value, "event": None,
                  "slot": attribute, "kind": "state", "state": state, "source_memory_id": turn}
    return MemoryUnit(
        memory_id=memory_id, kind=kind, text=text or f"{entity} · {attribute}: {value}",
        structured=structured, entity_ids=[entity.casefold()],
        t_event=Interval(start=event_start, precision="day") if event_start else Interval(precision="unknown"),
        t_ingest=Interval(start=ingest_start, precision="session") if ingest_start else Interval(precision="unknown"),
        valid_interval=Interval(start=event_start, end=valid_end, precision="day") if event_start else None,
        evidence=[Span(turn, value)],
    )


def merge_date(value):
    return use.model.parse_time(value)


def candidate(memory_id, channel="bm25", rank=1, score=1.0):
    return Candidate(memory_id=memory_id, channel=channel, rank=rank, raw_score=score,
                     score=score, stage_scores={channel: score},
                     provenance={"retriever": channel})


def retrieval_result(store, channels, query="question", gold_frame=None):
    frame = gold_frame or QueryFrame(query=query)
    merged, seen = [], set()
    for ranking in channels.values():
        for item in ranking:
            if item.memory_id not in seen:
                seen.add(item.memory_id)
                merged.append(item)
    return RetrievalResult(frame=frame, plan=Plan(nodes=[], parallel_groups=[]),
                           candidates=merged, trace=[], k=15, by_channel=channels)


class FusionTests(unittest.TestCase):
    def setUp(self):
        self.store = store_module.MemoryStore([
            unit("a", value="alpha"), unit("b", value="beta"), unit("c", value="gamma"),
        ])
        self.frame = QueryFrame(query="question", intent="single_hop")
        self.channels = {
            "bm25": [candidate("a", "bm25", 1, 2.0), candidate("b", "bm25", 2, 1.0)],
            "dense": [candidate("b", "dense", 1, 0.9), candidate("c", "dense", 2, 0.5)],
        }

    def test_rrf_rewards_agreement(self):
        fused = merge.RRFFusion(rrf_k=60).fuse(self.channels, self.frame, None)
        self.assertEqual(fused[0].memory_id, "b")
        self.assertEqual(fused[0].channel, "fusion")
        self.assertIn("bm25", fused[0].provenance["channels"])

    def test_weighted_rrf_uses_channel_weights(self):
        fused = merge.WeightedRRFFusion(rrf_k=60, weights={"bm25": 10.0, "dense": 0.01}).fuse(
            self.channels, self.frame, None)
        self.assertEqual(fused[0].memory_id, "a")

    def test_single_channel_and_linear(self):
        fused = merge.SingleChannelFusion(channel="dense").fuse(self.channels, self.frame, None)
        self.assertEqual([item.memory_id for item in fused], ["b", "c"])
        linear = merge.LinearFusion(alpha=0.5).fuse(self.channels, self.frame, None)
        self.assertTrue(linear)
        self.assertTrue(all(item.stage_scores["fusion"] is not None for item in linear))

    def test_query_adaptive_prefers_temporal_for_temporal_queries(self):
        frame = QueryFrame(query="when?", intent="temporal")
        channels = {
            "bm25": [candidate("b", "bm25", 1, 1.0)],
            "temporal": [candidate("a", "temporal", 1, 1.0)],
        }
        fused = merge.QueryAdaptiveFusion(base_weights={"bm25": 0.35, "temporal": 0.30}).fuse(
            channels, frame, None)
        self.assertEqual(fused[0].memory_id, "a")

    def test_ndcg_is_bounded(self):
        candidates = [candidate("a"), candidate("b"), candidate("c")]
        score = merge.ndcg_at_k(self.store, candidates, ["D1:1"])
        self.assertIsNotNone(score)
        self.assertLessEqual(score, 1.0)
        self.assertGreaterEqual(score, 0.0)


class PostTests(unittest.TestCase):
    def setUp(self):
        self.store = store_module.MemoryStore([
            unit("old", value="teacher", state="HISTORICAL", event="2023-01-01"),
            unit("new", value="engineer", state="ACTIVE", event="2023-06-01"),
            unit("dup", value="teacher", state="ACTIVE", event="2023-06-01", turn="D2:1"),
        ])
        self.frame = QueryFrame(query="job")

    def test_mmr_promotes_novelty(self):
        candidates = [candidate("old", score=1.0), candidate("dup", score=0.9), candidate("new", score=0.9)]
        selected = merge.MMRPost(**{"lambda": 0.5}).apply(candidates, self.frame, self.store)
        self.assertEqual(selected[0].memory_id, "old")
        self.assertEqual(selected[1].memory_id, "new")

    def test_time_decay_prefers_recent(self):
        frame = QueryFrame(query="job", as_of=merge_date("2023-07-01"))
        candidates = [candidate("old", score=1.0), candidate("new", score=0.8)]
        decayed = merge.TimeDecayPost(**{"lambda": 0.01, "unit": "day", "except_history": False}).apply(candidates, frame, self.store)
        self.assertEqual(decayed[0].memory_id, "new")
        self.assertGreater(decayed[0].stage_scores["decay"], decayed[1].stage_scores["decay"])

    def test_extractive_compress_respects_budget(self):
        candidates = [candidate(memory_id) for memory_id in ("old", "new", "dup")]
        compressed = merge.ExtractiveCompress(budget_tokens=1).apply(candidates, self.frame, self.store)
        self.assertLess(len(compressed), len(candidates))
        self.assertGreaterEqual(len(compressed), 1)

    def test_threshold_filter_drops_stale_historical(self):
        candidates = [candidate("old"), candidate("new"), candidate("dup")]
        filtered = merge.ThresholdFilter(drop_stale=True).apply(candidates, self.frame, self.store)
        self.assertNotIn("old", {item.memory_id for item in filtered})

    def test_cross_encoder_falls_back_without_dependency(self):
        reranker = merge.CrossEncoderReranker(model="BAAI/bge-reranker-v2-m3")

        def fail(*args, **kwargs):
            raise ImportError("sentence-transformers is not installed")

        with patch.object(reranker, "_load", side_effect=fail):
            candidates, info = reranker.rerank([candidate("a"), candidate("b")], self.frame, self.store, None)
        self.assertTrue(info["fallback"])
        self.assertEqual([item.memory_id for item in candidates], ["a", "b"])

    def test_cross_encoder_with_injected_scorer(self):
        reranker = merge.CrossEncoderReranker(top_n=2)

        class Scorer:
            def predict(self, pairs):
                return [float(len(text)) for _, text in pairs]

        reranker._model = Scorer()
        candidates, info = reranker.rerank([candidate("a"), candidate("new")], self.frame, self.store, None)
        self.assertFalse(info["fallback"])
        self.assertEqual(candidates[0].memory_id, "new")

    def test_merge_waterfall_records_every_stage(self):
        data = retrieval_result(self.store, {
            "bm25": [candidate("old", score=2.0), candidate("new", score=1.5)],
            "dense": [candidate("new", score=0.9), candidate("dup", score=0.8)],
        })
        pipeline = merge.MergePipeline("rrf", "none", mmr="mmr", decay="time_decay", compress="extractive",
                                       params={"mmr": {"lambda": 0.7}, "decay": {"lambda": 0.001},
                                               "compress": {"budget_tokens": 1000}})
        result = pipeline.run(data, self.store, None, gold_turns=["D1:1"])
        stages = [row["stage"] for row in result.waterfall]
        self.assertEqual(stages, ["raw_channels", "after_fusion", "after_rerank", "after_filter",
                                  "after_mmr", "after_decay", "after_compress"])
        for row in result.waterfall:
            self.assertIn("recall", row)
            self.assertIn("ndcg", row)
            self.assertIn("tokens", row)
        self.assertGreater(result.tokens, 0)


class UseTests(unittest.TestCase):
    def setUp(self):
        self.store = store_module.MemoryStore([
            unit("valid", value="teacher", state="ACTIVE", event="2023-05-01"),
            unit("historical", value="student", state="HISTORICAL", event="2023-01-01",
                 end="2023-02-01"),
            unit("conflict", value="engineer", state="CONFLICT", event="2023-06-01"),
        ])
        self.store.conflicts = [("valid", "conflict")]
        self.frame = QueryFrame(query="job", as_of=merge_date("2023-05-15"))
        self.units = self.store.units

    def test_state_resolvers(self):
        none_view = use.NoneStateResolver().resolve(self.frame, self.units, self.store, None)
        self.assertEqual(len(none_view.valid), 3)
        offline = use.OfflineSlotResolver().resolve(self.frame, self.units, self.store, None)
        self.assertEqual([unit.memory_id for unit in offline.valid], ["valid", "conflict"])
        self.assertEqual([unit.memory_id for unit in offline.superseded], ["historical"])
        bitemporal = use.BitemporalResolver().resolve(self.frame, self.units, self.store, None)
        self.assertEqual([unit.memory_id for unit in bitemporal.valid], ["valid"])

    def test_query_llm_state_resolver(self):
        llm = FakeLLM(reply=lambda prompt: {"memories": [{"id": "valid", "state": "HISTORICAL"}]})
        view = use.QueryLLMResolver().resolve(self.frame, self.units, self.store,
                                              SimpleNamespace(llm=llm))
        self.assertIn("valid", {unit.memory_id for unit in view.superseded})

    def test_valid_history_filters_citations_and_answers(self):
        llm = FakeLLM(reply=lambda prompt: {"answer": "teacher", "citations": ["D1:1", "invented"]})
        pipeline = use.UsePipeline("offline_slot", "valid_history")
        result = pipeline.run("job", SimpleNamespace(units=self.store.units, tokens=10),
                              self.frame, self.store, SimpleNamespace(llm=llm))
        self.assertEqual(result.answer, "teacher")
        self.assertEqual(result.citations, ["D1:1"])
        self.assertFalse(result.refused)
        self.assertEqual(len(result.conflicts), 1)

    def test_direct_answerer(self):
        llm = FakeLLM(reply=lambda prompt: {"answer": "teacher", "citations": []})
        result = use.UsePipeline("none", "direct").run(
            "job", SimpleNamespace(units=self.store.units, tokens=5), self.frame,
            self.store, SimpleNamespace(llm=llm))
        self.assertEqual(result.answer, "teacher")
        self.assertFalse(result.refused)

    def test_citation_answerer_refuses_without_citation(self):
        llm = FakeLLM(reply=lambda prompt: {"answer": "teacher", "citations": []})
        result = use.UsePipeline("offline_slot", "citation_required").run(
            "job", SimpleNamespace(units=self.store.units, tokens=5), self.frame,
            self.store, SimpleNamespace(llm=llm))
        self.assertTrue(result.refused)
        self.assertEqual(result.answer, "unknown")

    def test_refusal_and_conflict_disclosure(self):
        llm = FakeLLM(reply=lambda prompt: {"answer": "unknown", "citations": []})
        result = use.UsePipeline("offline_slot", "valid_history").run(
            "job", SimpleNamespace(units=self.store.units, tokens=5), self.frame,
            self.store, SimpleNamespace(llm=llm))
        self.assertTrue(result.refused)
        self.assertEqual(result.conflicts, [("valid", "conflict")])

    def test_use_pipeline_refuses_when_no_llm(self):
        result = use.UsePipeline("none", "direct").run(
            "job", SimpleNamespace(units=self.store.units, tokens=5), self.frame,
            self.store, SimpleNamespace(llm=None))
        self.assertTrue(result.refused)
        self.assertEqual(result.answer, "unknown")


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.store = store_module.MemoryStore([
            unit("active", value="teacher", state="ACTIVE", event="2023-06-01"),
            unit("old", value="student", state="HISTORICAL", event="2022-01-01", start="2022-01-01T10:00"),
            unit("dup", value="teacher", state="ACTIVE", event="2023-06-01", turn="D2:1"),
            unit("contra", value="engineer", state="ACTIVE", event="2023-06-01"),
        ])

    def test_scan_reports_stale_contradictions_duplicates_and_metrics(self):
        report = maintenance.scan(self.store, as_of="2023-07-01", threshold=0.9)
        self.assertIn("old", report.stale)
        self.assertTrue(report.contradictions)
        self.assertIn("dup", report.duplicates)
        for key in ("staleness", "contradiction_rate", "update_correctness"):
            self.assertIn(key, report.metrics)
            self.assertGreaterEqual(report.metrics[key], 0.0)
            self.assertLessEqual(report.metrics[key], 1.0)

    def test_forget_archive_keeps_the_unit_in_the_result(self):
        result = maintenance.forget(self.store, "archive", params={"age_days": 100}, as_of="2023-07-01")
        self.assertIn("old", result.removed)
        self.assertNotIn("old", self.store)
        self.assertEqual([unit.memory_id for unit in result.archived], ["old"])

    def test_forget_ttl_and_none(self):
        unchanged = maintenance.forget(self.store, "none", as_of="2023-07-01")
        self.assertEqual(unchanged.removed, [])
        result = maintenance.forget(self.store, "ttl", params={"ttl_days": 500}, as_of="2023-07-01")
        self.assertIn("old", result.removed)

    def test_consolidate_dedupe_removes_near_duplicates(self):
        result = maintenance.consolidate(self.store, "dedupe", params={"threshold": 0.9})
        self.assertIn("dup", result.removed)
        self.assertNotIn("dup", self.store)

    def test_update_applies_a_resolver_decision(self):
        incoming = [unit("updated", attribute="city", value="Paris", state="ACTIVE", event="2023-07-01")]
        result = maintenance.update(self.store, incoming, "mem0_4action")
        self.assertIsNotNone(result.decision)
        self.assertIn("updated", self.store)


class E2ETests(unittest.TestCase):
    def test_pipelines_build_from_b0_config_and_retrieval_exposes_channels(self):
        data = runtime_fixture()
        merger = merge.MergePipeline.from_config(data["runtime"])
        self.assertEqual((merger.fusion_name, merger.rerank_name), ("rrf", "none"))
        user = use.UsePipeline.from_config(data["runtime"])
        self.assertEqual((user.resolver_name, user.answerer_name), ("query_llm", "valid_history"))
        retrieval = RetrievalRunner().run("What did Caroline research?", data["runtime"], 5)
        self.assertTrue(retrieval.by_channel)
        self.assertTrue(all(retrieval.by_channel.values()))

    def test_ten_questions_cover_four_categories_and_full_trace(self):
        data = runtime_fixture()
        merger = merge.MergePipeline("rrf", "none")
        user = use.UsePipeline("offline_slot", "valid_history")
        pipeline = E2EPipeline(data["runtime"], merger=merger, user=user)
        categories, rows = set(), []
        for question in data["questions"]:
            result = pipeline.run(question["question"], k=15,
                                  gold_turns=evaluation.evidence_turns(question))
            categories.add(question.get("category"))
            self.assertTrue(result.merge.candidates)
            self.assertTrue(result.merge.waterfall)
            self.assertTrue(result.answer.answer)
            self.assertFalse(result.answer.refused)
            json.dumps(result.as_dict())
            rows.append({
                "category": question.get("category"),
                "tokens": result.tokens,
                "latency": result.latency_ms,
                "recall": result.merge.waterfall[-1]["recall"],
            })
        self.assertEqual(categories, {1, 2, 3, 4})
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["tokens"] > 0 for row in rows))
        E2ETests.rows = rows

    def test_two_m_and_two_u_candidates_are_measured(self):
        data = runtime_fixture()
        candidates_m = {
            "M1-rrf-none": merge.MergePipeline("rrf", "none"),
            "M2-weighted-rerank-compress": merge.MergePipeline(
                "weighted_rrf", "cross_encoder", compress="extractive",
                params={"fusion": {"rrf_k": 60, "weights": {"bm25": 1.0, "dense": 0.7, "temporal": 1.2}},
                        "compress": {"budget_tokens": 1000}}),
        }
        candidates_u = {
            "U1-direct": use.UsePipeline("none", "direct"),
            "U2-valid-history": use.UsePipeline("offline_slot", "valid_history"),
        }
        runner = RetrievalRunner()
        summaries = {}
        for m_name, merger in candidates_m.items():
            for u_name, user in candidates_u.items():
                rows = []
                for question in data["questions"]:
                    retrieval = runner.run(question["question"], data["runtime"], 15)
                    merged = merger.run(retrieval, data["store"], data["runtime"],
                                        gold_turns=evaluation.evidence_turns(question))
                    answer = user.run(question["question"], merged, retrieval.frame,
                                      data["store"], data["runtime"])
                    rows.append({"tokens": answer.tokens, "recall": merged.waterfall[-1]["recall"],
                                 "ndcg": merged.waterfall[-1]["ndcg"], "refused": answer.refused})
                summaries[f"{m_name}+{u_name}"] = {
                    "tokens": round(sum(row["tokens"] for row in rows) / len(rows), 2),
                    "recall": round(sum(row["recall"] or 0 for row in rows) / len(rows), 4),
                    "ndcg": round(sum(row["ndcg"] or 0 for row in rows) / len(rows), 4),
                    "refused": sum(1 for row in rows if row["refused"]),
                }
        self.assertEqual(len(summaries), 4)
        self.assertTrue(all(item["recall"] >= 0 for item in summaries.values()))
        E2ETests.matrix = summaries

    def test_p95_latency_and_token_waterfall(self):
        data = runtime_fixture()
        pipeline = E2EPipeline(data["runtime"], merger=merge.MergePipeline("rrf", "none"),
                               user=use.UsePipeline("offline_slot", "valid_history"))
        latencies, tokens = [], []
        for question in data["questions"]:
            result = pipeline.run(question["question"], k=15)
            latencies.append(result.latency_ms)
            tokens.append(result.tokens)
        latencies.sort()
        p95 = latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)]
        self.assertGreaterEqual(p95, latencies[0])
        self.assertTrue(all(value > 0 for value in tokens))
        E2ETests.p95 = p95
        E2ETests.tokens = round(sum(tokens) / len(tokens), 2)


if __name__ == "__main__":
    unittest.main()
