"""Unit tests. The language model is mocked; run with `python -m unittest discover -s tests`."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import server
from memwb import config, dataset, evaluation, extraction, llm, memory, pipeline, retrieval, states


def tiny_sample(sample_id="custom-1", text="hello"):
    return {"sample_id": sample_id, "conversation": {
        "speaker_a": "A", "speaker_b": "B",
        "session_1_date_time": "1:00 pm on 1 May, 2023",
        "session_1": [{"dia_id": "D1:1", "speaker": "A", "text": text}],
    }}


class StoreCase(unittest.TestCase):
    """Run each test against a temporary import directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = dataset.Store(import_dir=Path(self.tmp.name) / "imported")
        dataset.set_store(self.store)

    def tearDown(self):
        dataset.set_store(None)
        self.tmp.cleanup()


class DatasetTests(StoreCase):
    def test_course_split_is_four_dev_two_test_and_disjoint(self):
        self.assertEqual(len(config.SPLIT["development"]), 4)
        self.assertEqual(set(config.SPLIT["test"]), {"conv-41", "conv-42"})
        self.assertTrue(set(config.SPLIT["development"]).isdisjoint(config.SPLIT["test"]))

    def test_import_is_persistent_and_rejects_duplicate_ids(self):
        self.assertEqual(self.store.import_samples(tiny_sample()), ["custom-1"])
        with self.assertRaises(ValueError):
            self.store.import_samples(tiny_sample("CUSTOM-1"))
        reloaded = dataset.Store(import_dir=self.store.import_dir)
        self.assertIn("custom-1", reloaded.ids())

    def test_invalid_batch_writes_nothing(self):
        with self.assertRaises(ValueError):
            self.store.import_samples([tiny_sample("ok"), {"sample_id": "../../bad", "conversation": {}}])
        self.assertFalse(self.store.import_dir.exists() and any(self.store.import_dir.iterdir()))

    def test_batch_rolls_back_when_a_commit_fails(self):
        original, calls = Path.replace, []

        def flaky(path, target):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("disk error")
            return original(path, target)

        with patch.object(Path, "replace", flaky), self.assertRaises(OSError):
            self.store.import_samples([tiny_sample("a"), tiny_sample("b")])
        self.assertEqual(list(self.store.import_dir.iterdir()), [])
        self.assertNotIn("a", self.store.ids())


class MemoryTests(StoreCase):
    def setUp(self):
        super().setUp()
        self.turns, self.facts = memory.build(self.store.get("conv-26"))
        self.by_turn = {t["source"]["turn"]: t for t in self.turns}

    def test_turn_memory_keeps_content_time_and_source(self):
        t = self.by_turn["D19:1"]
        self.assertEqual(t["memory_id"], "conv26_D19_1")
        self.assertEqual(t["source"], {"conversation": "conv-26", "session": 19, "turn": "D19:1"})
        self.assertTrue(t["session_time"].startswith("2023-10-22"))
        self.assertIn("adoption agency interviews", t["content"])

    def test_fact_memories_link_back_to_their_turn(self):
        for fact in self.facts[:50]:
            self.assertIn(fact["source_memory_id"], {t["memory_id"] for t in self.turns})
            self.assertTrue(fact["memory_id"].startswith(fact["source_memory_id"] + "_f"))

    def test_relative_dates_use_the_recording_date(self):
        match = [x for x in self.by_turn["D19:1"]["resolved_time_expressions"] if x["expression"].lower() == "last friday"]
        self.assertEqual(match[0]["date"], "2023-10-20")
        self.assertEqual(memory.resolve_relative_dates("feels like just yesterday I got married", "1:00 pm on 1 May, 2023"), [])
        self.assertEqual(memory.resolve_relative_dates("last Friday", "2:00 pm on 20 October, 2023")[0]["date"], "2023-10-13")

    def test_cutoff_uses_recording_date_inclusive(self):
        earlier = memory.apply_cutoff(self.turns, "2023-05-08")
        self.assertIn("D1:3", {t["source"]["turn"] for t in earlier})
        self.assertNotIn("D2:8", {t["source"]["turn"] for t in earlier})
        with self.assertRaises(ValueError):
            memory.apply_cutoff(self.turns, "May 2023")

    def test_dataset_observations_keep_all_cited_turns(self):
        mapped = memory.dataset_observations({"observation": {"s1": {"Alex": [["Shared", "D1:1, D1:2"]]}}})
        self.assertEqual(mapped["D1:2"][0]["source_turns"], ["D1:1", "D1:2"])

    def test_status_is_consistent_with_relations(self):
        chain = {"status": {"a": "ACTIVE", "b": "ACTIVE", "c": "ACTIVE"},
                 "relations": [{"from": "a", "to": "b", "type": "SUPERSEDE"}, {"from": "b", "to": "c", "type": "CONFLICT"}]}
        self.assertEqual(memory.consistent_status(["a", "b", "c"], chain), {"a": "HISTORICAL", "b": "CONFLICT", "c": "CONFLICT"})


class RetrievalTests(StoreCase):
    def setUp(self):
        super().setUp()
        self.turns, self.facts = memory.build(self.store.get("conv-26"))

    def test_bm25_handles_inflection_and_question_words(self):
        top = retrieval.bm25("What did Caroline research?", self.turns, 5, self.facts)
        self.assertIn("D2:8", {x["source"]["turn"] for x in top})

    def test_rrf_rewards_agreement(self):
        a, b, c = self.turns[:3]
        fused = retrieval.rrf([[a, b], [b, c]], 3)
        self.assertEqual(fused[0]["memory_id"], b["memory_id"])

    def test_embedding_cache_only_embeds_new_items(self):
        calls = []

        def fake_embed(texts):
            calls.append(len(texts))
            return [[1.0, float(i)] for i in range(len(texts))]

        with tempfile.TemporaryDirectory() as directory, patch.object(config, "CACHE_DIR", Path(directory)), \
                patch.object(retrieval, "_memo", {}), patch.object(llm, "embed", side_effect=fake_embed):
            retrieval.embeddings_for(self.turns[:3])
            retrieval.embeddings_for(self.turns[:5])
        self.assertEqual(calls, [3, 2])


class LlmTests(unittest.TestCase):
    def test_generation_disables_truncation_and_detects_overflow(self):
        seen = []
        with patch.object(llm, "post", side_effect=lambda path, body: seen.append(body) or {"response": '{"a":1}', "prompt_eval_count": 3}):
            self.assertEqual(llm.generate("q", True), {"a": 1})
        self.assertIs(seen[0]["truncate"], False)
        self.assertIs(seen[0]["shift"], False)
        with patch.object(llm, "post", return_value={"response": "{}", "prompt_eval_count": 32767}), self.assertRaises(llm.ContextOverflow):
            llm.generate("q", True)

    def test_token_limit_is_an_error_not_a_partial_answer(self):
        with patch.object(llm, "post", return_value={"response": '{"a":', "prompt_eval_count": 3, "eval_count": 50}), self.assertRaises(ValueError):
            llm.generate("q", True, max_tokens=50)

    def test_cpu_only_options(self):
        with patch.dict("os.environ", {"MEMORY_CPU_ONLY": "1", "MEMORY_THREADS": "4"}):
            self.assertEqual(llm.model_options(), {"num_gpu": 0, "num_thread": 4})


class ExtractionTests(StoreCase):
    def test_extraction_refuses_missing_or_duplicate_turns(self):
        turns = memory.turn_memories(self.store.get("conv-26"))[:2]
        with patch.object(llm, "generate", return_value={"items": []}), self.assertRaises(ValueError):
            extraction.build(turns)
        dup = {"items": [{"turn": turns[0]["source"]["turn"], "facts": []}] * 2}
        with patch.object(llm, "generate", return_value=dup), self.assertRaises(ValueError):
            extraction.build(turns[:1])

    def test_service_errors_are_not_split(self):
        turns = memory.turn_memories(self.store.get("conv-26"))[:3]
        with patch.object(extraction, "build", side_effect=TimeoutError("busy")) as build, self.assertRaises(TimeoutError):
            extraction.build_resilient(turns)
        self.assertEqual(build.call_count, 1)


class StatesTests(StoreCase):
    def test_slot_assignment_falls_back_to_attribute_after_bad_output(self):
        _, facts = memory.build(self.store.get("conv-26"))
        with patch.object(llm, "generate", side_effect=ValueError("bad json")):
            out = states.assign_slots("Caroline", facts[:3], {}, log=lambda s: None)
        self.assertEqual(out[facts[0]["memory_id"]]["slot"], states.normalize_slot(facts[0]["attribute"]))

    def test_chain_ignores_invalid_or_backward_links(self):
        _, facts = memory.build(self.store.get("conv-26"))
        window = facts[:3]
        reply = {"relations": [{"i": 1, "prev": 0, "type": "UPDATE"}, {"i": 0, "prev": 2, "type": "UPDATE"}, {"i": 2, "prev": 1, "type": "MAYBE"}],
                 "status": [{"i": 0, "status": "HISTORICAL"}]}
        text = {f["source_memory_id"]: "x" for f in window}
        with patch.object(llm, "generate", return_value=reply):
            relations, status = states.resolve_chain("C", "slot", "", window, text)
        self.assertEqual([(r["from"], r["to"]) for r in relations], [(window[0]["memory_id"], window[1]["memory_id"])])
        self.assertEqual(status[window[0]["memory_id"]], "HISTORICAL")


def fake_facts(turns, slot="adoption"):
    """Two versions of one slot attached to the first two turns, linked by UPDATE."""
    a, b = turns[0], turns[1]
    base = {"kind": "state", "slot": slot, "slot_key": "x::" + slot, "attribute": "status", "entity": "X", "value": "v", "event": None}
    fa = {**base, "memory_id": a["memory_id"] + "_f0", "source_memory_id": a["memory_id"], "session_time": a["session_time"], "source": a["source"],
          "relations": [{"type": "UPDATE", "direction": "to", "memory_id": b["memory_id"] + "_f0", "reason": ""}]}
    fb = {**base, "memory_id": b["memory_id"] + "_f0", "source_memory_id": b["memory_id"], "session_time": b["session_time"], "source": b["source"],
          "relations": [{"type": "UPDATE", "direction": "from", "memory_id": a["memory_id"] + "_f0", "reason": ""}]}
    return [fa, fb]


class PipelineTests(StoreCase):
    def setUp(self):
        super().setUp()
        self.turns = memory.turn_memories(self.store.get("conv-26"))

    def test_as_of_rederives_validity(self):
        facts = fake_facts(self.turns)
        full = pipeline.facts_as_of(facts, {t["memory_id"] for t in self.turns})
        self.assertEqual(full[facts[0]["memory_id"]]["state"], "HISTORICAL")
        early = pipeline.facts_as_of(facts, {self.turns[0]["memory_id"]})
        self.assertEqual(early[facts[0]["memory_id"]]["state"], "ACTIVE")

    def test_graph_expansion_adds_other_versions(self):
        facts = {f["memory_id"]: f for f in fake_facts(self.turns)}
        added = pipeline.graph_expand([self.turns[0]], self.turns, facts, 5)
        self.assertEqual([m["memory_id"] for m in added], [self.turns[1]["memory_id"]])

    def _run(self, replies, retrieved, method="dynamic", facts=None):
        with patch.object(memory, "build", return_value=(self.turns, facts or [])), \
                patch.object(retrieval, "hybrid", return_value=retrieved), patch.object(retrieval, "vector", return_value=retrieved), \
                patch.object(llm, "generate", side_effect=replies) as gen:
            return pipeline.answer("conv-26", "question", method, len(retrieved)), gen

    def test_dynamic_answers_from_valid_memories_only(self):
        a, b, c = self.turns[:3]
        states_reply = {"memories": [{"id": a["memory_id"], "state": "ACTIVE"}, {"id": b["memory_id"], "state": "HISTORICAL"},
                                     {"id": c["memory_id"], "state": "IRRELEVANT"}], "relations": []}
        out, gen = self._run([states_reply, {"answer": "ok"}], [a, b, c])
        prompt = gen.call_args_list[1].args[0]
        valid_part, superseded_part = prompt.split("Superseded memories:")
        self.assertIn(a["memory_id"], valid_part)
        self.assertIn(b["memory_id"], superseded_part)
        self.assertNotIn(c["memory_id"], prompt)
        self.assertEqual(out["valid_memory_ids"], [a["memory_id"]])

    def test_invented_ids_and_self_links_are_dropped(self):
        a, b = self.turns[:2]
        reply = {"memories": [{"id": a["memory_id"], "state": "ACTIVE"}, {"id": "invented", "state": "ACTIVE"}],
                 "relations": [{"from_id": a["memory_id"], "to_id": a["memory_id"], "type": "UPDATE"}, {"from_id": "invented", "to_id": b["memory_id"], "type": "UPDATE"}]}
        out, _ = self._run([reply, {"answer": "ok"}], [a, b])
        self.assertEqual(out["relations"], [])
        self.assertEqual({m["id"] for m in out["memories"]}, {a["memory_id"], b["memory_id"]})

    def test_contradictory_states_are_retried_then_rejected(self):
        a = self.turns[0]
        reply = {"memories": [{"id": a["memory_id"], "state": "ACTIVE"}, {"id": a["memory_id"], "state": "HISTORICAL"}], "relations": []}
        with self.assertRaises(ValueError):
            self._run([reply, reply], [a])
        out, gen = self._run([reply, {"memories": [{"id": a["memory_id"], "state": "ACTIVE"}], "relations": []}, {"answer": "ok"}], [a])
        self.assertEqual(gen.call_count, 3)
        self.assertEqual(out["answer"], "ok")

    def test_identical_duplicate_states_are_merged(self):
        a = self.turns[0]
        reply = {"memories": [{"id": a["memory_id"], "state": "ACTIVE"}, {"id": a["memory_id"], "state": "ACTIVE"}], "relations": []}
        out, _ = self._run([reply, {"answer": "ok"}], [a])
        self.assertEqual(len(out["memories"]), 1)

    def test_unbacked_relation_is_reviewed_and_can_be_rejected(self):
        a, b = self.turns[:2]
        reply = {"memories": [{"id": a["memory_id"], "state": "HISTORICAL"}, {"id": b["memory_id"], "state": "ACTIVE"}],
                 "relations": [{"from_id": a["memory_id"], "to_id": b["memory_id"], "type": "UPDATE", "reason": "same word"}]}
        review = {"accepted": [], "rejected": [{"index": 0, "reason": "insufficient evidence"}]}
        out, gen = self._run([reply, review, {"answer": "ok"}], [a, b])
        self.assertEqual(gen.call_count, 3)
        self.assertEqual(out["relations"], [])
        self.assertEqual(out["rejected_relations"][0]["review_reason"], "insufficient evidence")

    def test_same_slot_relation_skips_review_and_marks_earlier_historical(self):
        a, b = self.turns[:2]
        reply = {"memories": [{"id": a["memory_id"], "state": "ACTIVE"}, {"id": b["memory_id"], "state": "ACTIVE"}],
                 "relations": [{"from_id": a["memory_id"], "to_id": b["memory_id"], "type": "UPDATE"}]}
        out, gen = self._run([reply, {"answer": "ok"}], [a, b], facts=fake_facts(self.turns))
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(out["relations"][0]["support"], "memory_graph")
        self.assertEqual({m["id"]: m["state"] for m in out["memories"]}[a["memory_id"]], "HISTORICAL")

    def test_baselines_share_answer_format(self):
        out, gen = self._run([{"answer": "x"}], self.turns[:2], method="hybrid")
        self.assertEqual(out["answer"], "x")
        self.assertEqual(gen.call_count, 1)


class EvaluationTests(unittest.TestCase):
    def test_f1_follows_locomo_conventions(self):
        self.assertEqual(evaluation.token_f1("a red ball", "red ball"), 1.0)
        self.assertEqual(evaluation.answer_f1("Paris, Rome", "Rome, Paris", 1), 1.0)
        self.assertEqual(evaluation.answer_f1("hiking", "hiking; outdoors", 3), 1.0)

    def test_unanswerable_category_is_excluded(self):
        qa = [{"category": 5, "adversarial_answer": "x"}, {"category": 1, "answer": "yes"}, {"category": 2, "answer": "a"}]
        self.assertEqual([i for i, _ in evaluation.answerable(qa)], [1, 2])

    def test_stratified_selection_cycles_categories(self):
        qa = [{"category": c, "answer": "a"} for c in (1, 1, 2, 2, 3, 4)]
        self.assertEqual([q["category"] for _, q in sorted(evaluation.stratified(qa, 4), key=lambda x: x[1]["category"])], [1, 2, 3, 4])

    def test_errors_count_as_zero(self):
        rows = [{"method": "vector", "category": 1, "answer_f1": 1.0, "evidence_recall": 1.0, "seconds": 1},
                {"method": "vector", "category": 1, "error": "x", "seconds": 1}]
        summary = evaluation.summarize_qa(rows)["vector"]
        self.assertEqual(summary["f1"], 0.5)
        self.assertEqual(summary["f1_success_only"], 1.0)

    def test_evidence_turns_are_normalised(self):
        self.assertEqual(evaluation.evidence_turns({"evidence": ["D8:6; D9:17", "D1:2"]}), ["D1:2", "D8:6", "D9:17"])


class HttpTests(StoreCase):
    def setUp(self):
        super().setUp()
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def post(self, path, body, kind="application/json"):
        return urllib.request.urlopen(urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers={"Content-Type": kind}))

    def test_static_files_and_traversal(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn(b"Memory Vault", r.read())
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(self.base + "/../server.py")
        self.assertEqual(err.exception.code, 404)

    def test_import_content_type_and_duplicates(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post("/api/import", tiny_sample("api-test"), "text/plain")
        self.assertEqual(err.exception.code, 415)
        with self.post("/api/import", tiny_sample("api-test")) as r:
            self.assertEqual(json.load(r)["imported"], ["api-test"])
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post("/api/import", tiny_sample("api-test"))
        self.assertEqual(err.exception.code, 400)

    def test_unknown_conversation_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(self.base + "/api/memories?sample=nope")
        self.assertEqual(err.exception.code, 404)

    def test_export_has_unified_schema(self):
        with urllib.request.urlopen(self.base + "/api/export?sample=conv-26") as r:
            data = json.load(r)
        self.assertEqual(data["schema"], "dynamic-memory-workbench/memory-export@1")
        m = data["memories"][0]
        for key in ("memory_id", "content", "entity", "timestamp", "source", "state", "relations", "source_text"):
            self.assertIn(key, m)


if __name__ == "__main__":
    unittest.main()
