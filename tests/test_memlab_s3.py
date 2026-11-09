"""S3 tests: W extract/resolve/audit, S indexes/graph/ceiling, R analyze/plan/retrieve."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from memlab import cache, config as lab_config, ingest, model, retrieve, runtime, store as store_module, write
from memlab.contracts import Interval, MemoryUnit, Relation, Span, WriteDecision
from memwb import dataset, evaluation, memory, pipeline, retrieval as legacy_retrieval

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
    """Deterministic local vectors so dense retrieval works without Ollama."""

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
        return "sha256:" + hashlib.sha256(b"fake-embedding").hexdigest()

    def usage(self):
        return {"calls": 0, "errors": 0}


def fixture():
    global _FIXTURE
    if _FIXTURE is None:
        data = lab_config.RunConfig.load(REFERENCE_B0).to_dict()
        data["planner"] = {"impl": "rule_router", "params": {}}
        config = lab_config.RunConfig.from_dict(data)
        sample = dataset.store().get("conv-26")
        turns, facts = memory.build(sample)
        embedding = FakeEmbedding()
        runtime_ = runtime.Runtime(config, embedding=embedding,
                                   cache=cache.ArtifactCache(Path(_TMP.name) / "artifacts"))
        ingested = ingest.build_store(sample, runtime_)
        runtime_.attach_store(ingested.store)
        questions = [question for _, question in evaluation.stratified(sample.get("qa", []), 10)]
        _FIXTURE = {
            "config": config, "sample": sample, "turns": turns, "facts": facts,
            "embedding": embedding, "runtime": runtime_, "ingested": ingested,
            "store": ingested.store, "questions": questions,
        }
    return _FIXTURE


def fact_unit(memory_id="f1", *, entity="Caroline", attribute="job", value="teacher",
              slot="job", state="ACTIVE", session_time="2023-05-01T10:00",
              resolved_date=None, source_turn="D1:1", text=None):
    event = model.parse_time(resolved_date)
    ingest_time = model.parse_time(session_time)
    valid = Interval(start=event, precision="day") if event else Interval(precision="unknown")
    return MemoryUnit(
        memory_id=memory_id, kind="fact",
        text=text or f"{entity} · {attribute}: {value}",
        structured={"entity": entity, "attribute": attribute, "value": value, "event": None,
                    "time_expression": None, "resolved_date": resolved_date, "slot": slot,
                    "kind": "state", "state": state, "source_memory_id": source_turn},
        entity_ids=[entity.casefold()],
        t_event=Interval(start=event, precision="day") if event else Interval(precision="unknown"),
        t_ingest=Interval(start=ingest_time, precision="session") if ingest_time else Interval(precision="unknown"),
        valid_interval=valid,
        evidence=[Span(source_turn, value)],
    )


def turn_unit(memory_id="t1", *, turn="D1:1", text="Caroline went to the LGBTQ support group yesterday",
              entity="Caroline", session_time="2023-05-08T13:56"):
    moment = model.parse_time(session_time)
    interval = Interval(start=moment, precision="session") if moment else Interval(precision="unknown")
    return MemoryUnit(
        memory_id=memory_id, kind="turn", text=text,
        structured={"speaker": entity, "session": 1, "turn": turn, "state": "ACTIVE", "fact_ids": []},
        entity_ids=[entity.casefold()], t_event=interval, t_ingest=interval,
        evidence=[Span(turn, text)], provenance={"source": {"conversation": "conv-26"}},
    )


class WriteTests(unittest.TestCase):
    def test_legacy_flat_extracts_cached_facts_for_one_turn(self):
        data = fixture()
        extractor = write.LegacyFlatExtractor()
        turn = next(unit for unit in model.from_sample(data["sample"]).units
                    if unit.kind == "turn" and unit.structured["turn"] == "D1:3")
        units = extractor.extract(turn, data["runtime"])
        self.assertTrue(units)
        self.assertTrue(all(unit.kind == "fact" for unit in units))
        self.assertEqual(units[0].provenance["extractor"], "legacy_flat")
        self.assertEqual(units[0].structured["source_memory_id"], "conv26_D1_3")

    def test_meta_schema_adds_fact_temporal_relation_evidence_dimensions(self):
        data = fixture()
        extractor = write.MetaSchemaExtractor(fields=8, bitemporal=True)
        turn = next(unit for unit in model.from_sample(data["sample"]).units
                    if unit.kind == "turn" and unit.structured["turn"] == "D1:3")
        units = extractor.extract(turn, data["runtime"])
        self.assertTrue(units)
        structured = units[0].structured
        for key in ("fact", "temporal", "relation", "evidence", "schema"):
            self.assertIn(key, structured)
        self.assertEqual(structured["schema"]["fields"], 8)
        self.assertIn("t_event", structured["temporal"])
        self.assertEqual(units[0].provenance["extractor"], "meta_schema")

    def test_resolvers_return_decisions_and_never_mutate_the_store(self):
        existing = fact_unit("old", value="teacher at a school")
        store = store_module.MemoryStore([existing])
        incoming = [fact_unit("dup", value="teacher at a school"),
                    fact_unit("new", value="software engineer at a bank"),
                    fact_unit("other", attribute="hobby", value="painting")]
        cases = {
            "append": write.AppendResolver(),
            "keep_both": write.KeepBothResolver(),
            "overwrite": write.OverwriteResolver(),
            "mem0_4action": write.Mem0FourActionResolver(threshold=0.9),
        }
        for name, resolver in cases.items():
            decision = resolver.resolve(incoming, store, None)
            self.assertIsInstance(decision, WriteDecision)
            self.assertEqual(len(store.units), 1, msg=name)
        self.assertEqual(len(cases["append"].resolve(incoming, store, None).add), 3)
        keep = cases["keep_both"].resolve(incoming, store, None)
        self.assertEqual([unit.memory_id for unit in keep.add], ["new", "other"])
        overwrite = cases["overwrite"].resolve(incoming, store, None)
        self.assertEqual([old for old, _ in overwrite.update], ["old"])
        self.assertEqual(overwrite.relations[0].type, "UPDATE")
        mem0 = cases["mem0_4action"].resolve(incoming, store, None)
        self.assertEqual([unit.memory_id for unit in mem0.add], ["other"])
        self.assertEqual([unit.memory_id for unit in mem0.noop], ["dup"])
        self.assertEqual([old for old, _ in mem0.update], ["old"])

    def test_llm_audit_can_reject_a_rule_relation(self):
        relation = Relation("r1", "a", "b", "UPDATE", provenance={"support": "rule"})
        decision = WriteDecision(add=[], update=[], delete=[], noop=[], relations=[relation],
                                 conflicts=[], reasons={})

        class FakeLLM:
            def __init__(self, accepted):
                self.accepted = accepted

            def generate(self, prompt, json_mode=False):
                return {"accepted": self.accepted}

        kept = write.LLMAudit(max_pairs=8).audit(decision, SimpleNamespace(llm=FakeLLM([0])))
        self.assertEqual(len(kept.relations), 1)
        rejected = write.LLMAudit(max_pairs=8).audit(decision, SimpleNamespace(llm=FakeLLM([])))
        self.assertEqual(rejected.relations, [])
        self.assertIs(write.NoAudit().audit(decision, None), decision)

    def test_pipeline_writes_units_and_caches_extraction(self):
        data = fixture()
        turns = [turn_unit("t1", text="Caroline adopted a dog"), turn_unit("t2", turn="D9:9")]
        pipeline = write.WritePipeline("legacy_flat", "append", "none")
        first_store = store_module.MemoryStore(turns)
        first = pipeline.write(turns, first_store, data["runtime"])
        self.assertEqual(first.counts["add"], 0)  # no cached legacy facts for these synthetic turns
        self.assertIn("cache hit 0, miss 2", first.trace[0]["detail"])
        second = pipeline.write(turns, store_module.MemoryStore(turns), data["runtime"])
        self.assertIn("cache hit 2, miss 0", second.trace[0]["detail"])


class StoreTests(unittest.TestCase):
    def test_store_applies_add_update_delete_and_relations(self):
        store = store_module.MemoryStore([fact_unit("a", value="one")])
        decision = WriteDecision(
            add=[fact_unit("b", value="two")],
            update=[("a", fact_unit("a2", value="three"))],
            delete=[],
            noop=[],
            relations=[Relation("r1", "a2", "b", "RETAIN")],
            conflicts=[], reasons={},
        )
        store.apply(decision)
        self.assertIsNone(store.get("a"))
        self.assertEqual(store.get("a2").structured["value"], "three")
        self.assertIn("b", store)
        self.assertEqual(len(store.relations), 1)

    def test_bm25_index_finds_the_evidence_turn(self):
        store = store_module.MemoryStore([
            turn_unit("t1", text="Caroline went to the LGBTQ support group yesterday"),
            turn_unit("t2", turn="D2:1", text="Melanie painted a sunset"),
        ])
        scores = store.bm25_scores("LGBTQ support group")
        self.assertEqual(max(scores, key=scores.get), "t1")
        self.assertIn("units", store.lexical_stats())

    def test_dense_index_and_content_hash_are_stable(self):
        store = store_module.MemoryStore([turn_unit("t1"), turn_unit("t2", turn="D2:1", text="painting")])
        first_hash = store.index_hash
        self.assertEqual(first_hash, store.index_hash)
        scores = store.dense_scores("LGBTQ support group", FakeEmbedding())
        self.assertEqual(set(scores), {"t1", "t2"})
        store.add(turn_unit("t3", turn="D3:3", text="a new memory"))
        self.assertNotEqual(first_hash, store.index_hash)

    def test_temporal_filter_respects_event_and_ingest_time(self):
        dated = fact_unit("dated", resolved_date="2023-05-07", session_time="2023-05-08T13:56")
        undated = fact_unit("undated", resolved_date=None, session_time="2023-05-08T13:56")
        store = store_module.MemoryStore([dated, undated])
        self.assertEqual([unit.memory_id for unit in store.temporal_units(model.parse_time("2023-05-01"))],
                         [])
        self.assertEqual({unit.memory_id for unit in store.temporal_units(model.parse_time("2023-05-09"))},
                         {"dated", "undated"})

    def test_retrieval_ceiling_detects_missing_gold_evidence(self):
        store = store_module.MemoryStore([turn_unit("t1", turn="D1:1")])
        ceiling = store.ceiling(["D1:1", "D9:9"])
        self.assertEqual(ceiling["gold"], 2)
        self.assertEqual(ceiling["indexed"], 1)
        self.assertEqual(ceiling["recall"], 0.5)
        self.assertEqual(ceiling["missing"], ["D9:9"])

    def test_graph_representations_register_and_build(self):
        units = [turn_unit("t1"), fact_unit("f1", source_turn="D1:1"),
                 fact_unit("f2", value="engineer", source_turn="D2:1")]
        relations = [Relation("r1", "f1", "f2", "UPDATE")]
        for representation in ("state_slot", "entity_triple", "three_layer"):
            store = store_module.MemoryStore(units)
            store.apply(WriteDecision([], [], [], [], relations, [], {}))
            graph = store.ensure_graph(representation)
            self.assertEqual(graph.representation, representation)
            self.assertGreater(graph.stats()["edges"], 0)
            store.ensure_graph()  # keeps the built representation
            self.assertEqual(store.graph.representation, representation)


class AnalyzerPlannerTests(unittest.TestCase):
    def test_none_analyzer_and_planner(self):
        frame = retrieve.NoneAnalyzer().analyze("Who is Caroline?", None)
        self.assertEqual(frame.intent, "none")
        plan = retrieve.NonePlanner().plan(frame, None)
        self.assertEqual([(node.channel, node.depends_on) for node in plan.nodes], [("bm25", [])])

    def test_rule_analyzer_detects_temporal_and_multi_hop(self):
        analyzer = retrieve.RuleAnalyzer()
        temporal = analyzer.analyze("When did Caroline go to the support group?", None)
        self.assertEqual(temporal.intent, "temporal")
        self.assertTrue(temporal.temporal["time_intent"])
        multi = analyzer.analyze("How did Caroline and Melanie meet and then move?", None)
        self.assertEqual(multi.intent, "multi_hop")
        self.assertGreater(multi.complexity, 0.25)
        dated = analyzer.analyze("What was Caroline's job as of 2023-05-08?", None)
        self.assertEqual(dated.as_of.isoformat(timespec="minutes"), "2023-05-08T00:00")

    def test_rule_router_and_dag_plans(self):
        analyzer = retrieve.RuleAnalyzer()
        single = analyzer.analyze("Who is Caroline?", None)
        router = retrieve.RuleRouterPlanner().plan(single, None)
        self.assertEqual([node.channel for node in router.nodes], ["bm25", "dense"])
        temporal = analyzer.analyze("When did Caroline move?", None)
        self.assertEqual([node.channel for node in retrieve.RuleRouterPlanner().plan(temporal, None).nodes],
                         ["temporal", "bm25"])
        multi = analyzer.analyze("How did Caroline and Melanie meet and then move?", None)
        plan = retrieve.DagPlanner().plan(multi, None)
        if multi.intent == "multi_hop":
            self.assertEqual(plan.nodes[1].depends_on, ["n1"])
            self.assertEqual(plan.nodes[1].channel, "graph_khop")


class RetrieverTests(unittest.TestCase):
    def ctx(self, store):
        return SimpleNamespace(store=store, embedding=FakeEmbedding(),
                                config=fixture()["config"], cache=cache.ArtifactCache(Path(_TMP.name) / "r"))

    def test_bm25_and_dense_return_candidates(self):
        store = store_module.MemoryStore([turn_unit("t1"), turn_unit("t2", turn="D2:1", text="painting")])
        ctx = self.ctx(store)
        frame = retrieve.RuleAnalyzer().analyze("LGBTQ support group", ctx)
        node = retrieve.PlanNode("n1", frame.query, "bm25")
        bm25 = retrieve.BM25Retriever().retrieve(frame, node, 5, ctx)
        self.assertEqual(bm25[0].memory_id, "t1")
        self.assertIsInstance(bm25[0], retrieve.Candidate)
        dense = retrieve.DenseRetriever().retrieve(frame, retrieve.PlanNode("n1", frame.query, "dense"), 5, ctx)
        self.assertEqual(len(dense), 2)
        self.assertEqual(dense[0].channel, "dense")

    def test_graph_khop_expands_from_evidence_turn(self):
        units = [turn_unit("t1"), fact_unit("f1", source_turn="D1:1"),
                 fact_unit("f2", value="engineer", source_turn="D2:1")]
        store = store_module.MemoryStore(units)
        store.apply(WriteDecision([], [], [], [], [Relation("r1", "f1", "f2", "UPDATE")], [], {}))
        store.ensure_graph("state_slot")
        ctx = self.ctx(store)
        frame = retrieve.RuleAnalyzer().analyze("Caroline job", ctx)
        node = retrieve.PlanNode("n1", frame.query, "graph_khop", filters={"seed_ids": ["t1"]})
        candidates = retrieve.GraphKHopRetriever().retrieve(frame, node, 5, ctx)
        self.assertIn("f1", {candidate.memory_id for candidate in candidates})
        self.assertEqual(candidates[0].provenance["representation"], "state_slot")

    def test_temporal_retriever_filters_by_as_of(self):
        units = [fact_unit("old", value="teacher", resolved_date="2023-05-01"),
                 fact_unit("new", value="engineer", resolved_date="2023-06-01")]
        ctx = self.ctx(store_module.MemoryStore(units))
        frame = retrieve.RuleAnalyzer().analyze("What was Caroline's job as of 2023-05-08?", ctx)
        candidates = retrieve.TemporalRetriever().retrieve(
            frame, retrieve.PlanNode("n2", frame.query, "temporal"), 5, ctx)
        self.assertEqual({candidate.memory_id for candidate in candidates}, {"old"})


class SmokeTests(unittest.TestCase):
    def test_ten_questions_return_candidates_and_trace(self):
        data = fixture()
        runner = retrieve.RetrievalRunner()
        rows = []
        for question in data["questions"]:
            result = runner.run(question["question"], data["runtime"], k=15)
            self.assertTrue(result.candidates)
            self.assertLessEqual(len(result.candidates), 15)
            ids = {candidate.memory_id for candidate in result.candidates}
            self.assertTrue(all(memory_id in data["store"] for memory_id in ids))
            names = {step["name"] for step in result.trace}
            self.assertIn("analyze", names)
            self.assertIn("plan", names)
            self.assertIn("merge", names)
            json.dumps(result.as_dict())  # trace/candidates stay JSON-serialisable
            ceiling = data["store"].ceiling(evaluation.evidence_turns(question))
            rows.append({"question": question["question"], "ceiling": ceiling["recall"],
                         "candidates": len(result.candidates)})
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["candidates"] > 0 for row in rows))
        self.assertGreaterEqual(sum(row["ceiling"] or 0 for row in rows) / 10, 0.9)

    def test_runtime_convenience_build_and_retrieve(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as directory:
            rt = runtime.Runtime(data["config"], embedding=data["embedding"],
                                 cache=cache.ArtifactCache(Path(directory)))
            result = rt.build_store("conv-26")
            self.assertIs(rt.store, result.store)
            self.assertEqual(len(result.store.facts), len(data["store"].facts))
            retrieval_result = rt.retrieve("What did Caroline research?", k=5)
            self.assertTrue(retrieval_result.candidates)
            self.assertLessEqual(len(retrieval_result.candidates), 5)

    def test_second_query_hits_the_retrieval_cache(self):
        data = fixture()
        runner = retrieve.RetrievalRunner()
        runner.run("When did Caroline go to the LGBTQ support group?", data["runtime"], k=5)
        second = runner.run("When did Caroline go to the LGBTQ support group?", data["runtime"], k=5)
        channel_lines = [step["detail"] for step in second.trace if step["name"].startswith("channel:")]
        self.assertTrue(channel_lines)
        self.assertTrue(all("cache hit" in line for line in channel_lines))

    def test_legacy_baseline_comparison_is_recorded(self):
        data = fixture()
        runner = retrieve.RetrievalRunner()
        embedding = data["embedding"]
        rows = []
        facts_by_id = {fact["memory_id"]: fact for fact in data["facts"]}
        with patch.object(legacy_retrieval, "embeddings_for",
                          side_effect=lambda items: [embedding.embed([f"{item['entity']}: {item['content']}"])[0]
                                                     for item in items]):
            for question in data["questions"]:
                gold = evaluation.evidence_turns(question)
                # dynamic retrieval = hybrid top-15 + same-slot expansion (limit 8)
                legacy_base = legacy_retrieval.hybrid(
                    question["question"], data["turns"], 15, facts=data["facts"],
                    query_vector=embedding.embed([question["question"]])[0])
                legacy_extra = pipeline.graph_expand(legacy_base, data["turns"], facts_by_id, 8)
                legacy = sorted(legacy_base + legacy_extra,
                                key=lambda item: (item["session_time"] or "", item["source"]["session"]))
                legacy_turns = [item["source"]["turn"] for item in legacy]
                result = runner.run(question["question"], data["runtime"], k=15)
                new_turns = set()
                for candidate in result.candidates:
                    unit = data["store"].get(candidate.memory_id)
                    if unit is None:
                        continue
                    if unit.kind == "turn" and unit.structured.get("turn"):
                        new_turns.add(unit.structured["turn"])
                    new_turns.update(span.turn_id for span in unit.evidence)
                rows.append({
                    "question": question["question"],
                    "legacy_recall": evaluation.recall(gold, legacy_turns),
                    "new_recall": evaluation.recall(gold, sorted(new_turns)),
                    "legacy_candidates": len(legacy),
                    "new_candidates": len(result.candidates),
                })
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["legacy_recall"] is not None for row in rows))
        self.assertTrue(all(row["new_candidates"] > 0 for row in rows))
        SmokeTests.comparison = rows


if __name__ == "__main__":
    unittest.main()
