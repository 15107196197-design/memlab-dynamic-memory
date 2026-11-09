"""S1 tests: contracts, registry, run config, manifest, LLM wrapper, legacy parity."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memlab import config as lab_config
from memlab import contracts, legacy, manifest, registry, runtime
from memlab.llm import EmbeddingClient, LLMClient, fingerprint_environment
from memwb import config as legacy_config
from memwb import dataset, evaluation, llm, memory, pipeline, retrieval

REFERENCE_B0 = lab_config.ROOT / "configs" / "reference-b0.json"
REFERENCE_R0 = lab_config.ROOT / "configs" / "reference-r0.json"


class ContractTests(unittest.TestCase):
    def test_span_and_interval_validate_offsets_and_order(self):
        span = contracts.Span("D1:1", "quote", 2, 7)
        self.assertEqual((span.start, span.end), (2, 7))
        with self.assertRaises(ValueError):
            contracts.Span("D1:1", "quote", 7, 2)
        with self.assertRaises(ValueError):
            contracts.Span("", "quote")

    def test_memory_unit_defaults_and_invariants(self):
        unit = contracts.MemoryUnit("m1", "fact", "text", {"attribute": "x"})
        self.assertEqual(unit.schema_version, "2.0")
        self.assertEqual((unit.entity_ids, unit.evidence, unit.provenance), ([], [], {}))
        with self.assertRaises(ValueError):
            contracts.MemoryUnit("m2", "rumour", "text", {})
        with self.assertRaises(ValueError):
            contracts.MemoryUnit("m3", "fact", "text", {}, confidence=1.5)

    def test_relation_rejects_self_links(self):
        edge = contracts.Relation("r1", "a", "b", "UPDATE")
        self.assertEqual(edge.confidence, 1.0)
        with self.assertRaises(ValueError):
            contracts.Relation("r2", "a", "a", "RETAIN")

    def test_query_plan_candidate_and_state_view_are_plain_containers(self):
        frame = contracts.QueryFrame("what changed?", intent="temporal")
        node = contracts.PlanNode("n1", frame.query, "dense", k=5)
        plan = contracts.Plan([node], [["n1"]], rationale="single hop")
        candidate = contracts.Candidate("m1", "dense", 1, raw_score=0.4)
        candidate.stage_scores["fusion"] = 0.5  # per-instance dict, not shared
        self.assertEqual(contracts.Candidate("m2", "bm25", 2).stage_scores, {})
        view = contracts.StateView([], [], [], [], ["m1"])
        self.assertIsNone(view.as_of)
        self.assertEqual(plan.parallel_groups, [["n1"]])

    def test_write_decision_has_seven_buckets(self):
        decision = contracts.WriteDecision([], [], [], [], [], [], {})
        self.assertEqual(len(decision.__dataclass_fields__), 7)


class ConfigTests(unittest.TestCase):
    def test_reference_configs_load_and_validate(self):
        b0 = lab_config.RunConfig.load(REFERENCE_B0)
        r0 = lab_config.RunConfig.load(REFERENCE_R0)
        self.assertEqual((b0.preset, r0.preset), ("B0", "R0"))
        self.assertTrue(b0.config_hash.startswith("sha256:"))
        self.assertNotEqual(b0.config_hash, r0.config_hash)
        self.assertEqual(b0.method, "legacy_dynamic")
        self.assertEqual(b0.split, "development")
        self.assertEqual(b0.seed, 13)

    def test_config_hash_is_order_independent_and_parameter_sensitive(self):
        first = {"a": 1, "b": {"c": [1, 2]}}
        second = {"b": {"c": [1, 2]}, "a": 1}
        self.assertEqual(lab_config.canonical_json(first), lab_config.canonical_json(second))
        self.assertEqual(lab_config.digest(first), lab_config.digest(second))
        changed = copy.deepcopy(first)
        changed["b"]["c"][1] = 3
        self.assertNotEqual(lab_config.digest(first), lab_config.digest(changed))
        self.assertEqual(lab_config.RunConfig.from_dict(first).config_hash, lab_config.digest(first))

    def test_config_is_isolated_from_later_mutation(self):
        payload = lab_config.RunConfig.load(REFERENCE_B0).to_dict()
        cfg = lab_config.RunConfig.from_dict(payload)
        original_hash = cfg.config_hash
        payload["graph"]["repr"]["impl"] = "none"
        cfg.to_dict()["schema"]["impl"] = "meta_schema"
        self.assertEqual(cfg.config_hash, original_hash)
        self.assertEqual(cfg.impl("graph.repr"), "state_slot")

    def test_graph_none_with_graph_retrieval_is_rejected(self):
        data = lab_config.RunConfig.load(REFERENCE_B0).to_dict()
        data["graph"]["repr"]["impl"] = "none"
        with self.assertRaises(lab_config.ConfigError) as caught:
            lab_config.validate(data)
        message = str(caught.exception)
        self.assertIn("vector_only", message)
        self.assertIn("graph.repr=none", message)
        data["graph"]["retrieval"]["impl"] = "vector_only"
        lab_config.validate(data)  # now legal

    def test_slot_expand_requires_state_slot(self):
        data = lab_config.RunConfig.load(REFERENCE_R0).to_dict()
        data["graph"]["retrieval"]["impl"] = "slot_expand"
        with self.assertRaises(lab_config.ConfigError) as caught:
            lab_config.validate(data)
        self.assertIn("state_slot", str(caught.exception))

    def test_unknown_implementation_reports_available_ones(self):
        data = lab_config.RunConfig.load(REFERENCE_B0).to_dict()
        data["schema"]["impl"] = "teleport"
        with self.assertRaises(lab_config.ConfigError) as caught:
            lab_config.validate(data)
        self.assertIn("teleport", str(caught.exception))
        self.assertIn("legacy_flat", str(caught.exception))

    def test_bitemporal_requires_meta_schema_and_flag(self):
        data = lab_config.RunConfig.load(REFERENCE_R0).to_dict()
        data["schema"]["impl"] = "legacy_flat"
        with self.assertRaises(lab_config.ConfigError) as caught:
            lab_config.validate(data)
        self.assertIn("bitemporal", str(caught.exception))
        data = lab_config.RunConfig.load(REFERENCE_R0).to_dict()
        data["schema"]["params"]["bitemporal"] = False
        with self.assertRaises(lab_config.ConfigError):
            lab_config.validate(data)

    def test_malformed_json_and_structure_are_reported(self):
        with self.assertRaises(lab_config.ConfigError):
            lab_config.RunConfig.loads("{not json")
        with self.assertRaises(lab_config.ConfigError) as caught:
            lab_config.validate({"environment": {"llm": {"model": ""}}})
        self.assertIn("environment.llm.model", str(caught.exception))


class RegistryTests(unittest.TestCase):
    def test_duplicate_registration_is_an_error(self):
        registry.register("test.dup", "first")(type("First", (), {}))
        with self.assertRaises(ValueError) as caught:
            registry.register("test.dup", "first")(type("Second", (), {}))
        self.assertIn("already registered", str(caught.exception))
        self.assertIs(registry.get("test.dup", "first").__name__, "First")

    def test_unknown_implementation_lists_available(self):
        with self.assertRaises(registry.UnknownImplementation) as caught:
            registry.get("method", "legacy_missing")
        message = str(caught.exception)
        self.assertIn("available", message)
        self.assertIn("legacy_dynamic", message)
        self.assertNotIn('"', message)  # KeyError quoting removed

    def test_builtin_legacy_methods_are_registered(self):
        self.assertEqual(
            registry.list_implementations("method"),
            ["legacy_dynamic", "legacy_full", "legacy_hybrid", "legacy_vector"],
        )
        self.assertIn("method", registry.list_implementations())

    def test_build_validates_parameters(self):
        class Parametrised:
            @classmethod
            def validate_params(cls, params):
                if set(params) - {"k"}:
                    raise TypeError("unexpected")

            def __init__(self, k=1):
                self.k = k

        registry.register("test.dup", "params")(Parametrised)
        registry.register("test.dup", "plain")(type("Plain", (), {}))
        self.assertEqual(registry.build("test.dup", "params", {"k": 7}).k, 7)
        with self.assertRaises(TypeError):
            registry.build("test.dup", "params", {"nope": 1})
        with self.assertRaises(TypeError):
            registry.build("test.dup", "plain", {"k": 1})  # no validator, no params allowed


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.config = lab_config.RunConfig.load(REFERENCE_B0)
        self.prompts = {"state": "state prompt", "answer": "answer prompt"}

    def test_manifest_records_every_reproducibility_field(self):
        built = manifest.build_manifest(
            self.config, prompts=self.prompts, run_id="r-20261109-1000-b0",
            created_at="2026-11-09T10:00:00+08:00",
        )
        self.assertEqual(built.config_hash, self.config.config_hash)
        self.assertRegex(built.git_commit, r"^[0-9a-f]{7,40}$")
        self.assertTrue(built.dataset_hash.startswith("sha256:"))
        self.assertEqual(built.dataset_hash, manifest.file_hash(legacy_config.DATA_FILE))
        self.assertTrue(built.model_fingerprint.startswith("sha256:"))
        self.assertEqual(built.model_fingerprint, fingerprint_environment(self.config.get("environment")))
        self.assertEqual(built.seed, 13)
        self.assertEqual(built.judge["model"], "qwen3.8:27b-q4_K_M")
        self.assertEqual(built.prompt_hash, manifest.prompts_hash(self.prompts))
        self.assertEqual(built.split, "development")
        self.assertEqual(built.preset, "B0")
        self.assertEqual(built.created_at, "2026-11-09T10:00:00+08:00")
        self.assertEqual(built.run_id, "r-20261109-1000-b0")

    def test_prompt_change_changes_prompt_hash(self):
        first = manifest.build_manifest(self.config, prompts=self.prompts)
        second = manifest.build_manifest(self.config, prompts={**self.prompts, "answer": "changed"})
        self.assertNotEqual(first.prompt_hash, second.prompt_hash)
        self.assertEqual(first.config_hash, second.config_hash)

    def test_manifest_round_trips_through_json(self):
        built = manifest.build_manifest(self.config, prompts=self.prompts, run_id="r-test")
        with tempfile.TemporaryDirectory() as directory:
            path = built.write(Path(directory) / "runs" / "manifest.json")
            reloaded = manifest.RunManifest.read(path)
        self.assertEqual(reloaded, built)
        self.assertEqual(json.loads(built.to_json())["schema"], manifest.MANIFEST_SCHEMA)

    def test_dataset_hash_is_content_addressed(self):
        with tempfile.TemporaryDirectory() as directory:
            one, two = Path(directory) / "one.json", Path(directory) / "two.json"
            one.write_text("a", encoding="utf-8")
            two.write_text("b", encoding="utf-8")
            self.assertNotEqual(manifest.file_hash(one), manifest.file_hash(two))
            self.assertEqual(manifest.dataset_hash(one), manifest.file_hash(one))
            self.assertIsNone(manifest.dataset_hash(Path(directory) / "missing.json"))

    def test_run_id_has_the_documented_shape(self):
        run_id = manifest.new_run_id(self.config, created_at="2026-11-09T14:12:03+08:00")
        self.assertRegex(run_id, r"^r-20261109-1412-b0$")


class LLMClientTests(unittest.TestCase):
    def test_generation_keeps_the_legacy_body_and_records_usage(self):
        payload = {"response": '{"a": 1}', "prompt_eval_count": 7, "eval_count": 3}
        with patch.object(llm, "post", side_effect=lambda path, body, **kwargs: payload) as posted:
            client = LLMClient(model="test-model")
            self.assertEqual(client.generate("hello", json_mode=True), {"a": 1})
        body = posted.call_args.args[1]
        self.assertIs(body["truncate"], False)
        self.assertIs(body["shift"], False)
        self.assertEqual(body["model"], "test-model")
        record = client.calls[0]
        self.assertEqual((record.tokens_in, record.tokens_out), (7, 3))
        self.assertEqual(record.prompt_chars, 5)
        self.assertGreaterEqual(record.latency_ms, 0.0)
        self.assertIsNone(record.error)
        self.assertEqual(client.usage()["tokens_in"], 7)

    def test_default_model_matches_the_legacy_default(self):
        payload = {"response": "ok", "prompt_eval_count": 1, "eval_count": 1}
        with patch.dict("os.environ", {"MEMORY_MODEL": "env-model"}), \
                patch.object(llm, "post", side_effect=lambda path, body, **kwargs: payload) as posted:
            LLMClient().generate("q")
        self.assertEqual(posted.call_args.args[1]["model"], "env-model")

    def test_failures_are_recorded_and_reraised(self):
        client = LLMClient(model="test-model")
        with patch.object(llm, "post", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                client.generate("q", json_mode=True)
        record = client.calls[0]
        self.assertIn("RuntimeError: boom", record.error)
        self.assertIsNone(record.tokens_in)

    def test_usage_totals_across_calls(self):
        payloads = [{"response": "a", "prompt_eval_count": 7, "eval_count": 3},
                    {"response": "b", "prompt_eval_count": 5, "eval_count": 2}]
        client = LLMClient(model="test-model")
        with patch.object(llm, "post", side_effect=payloads):
            client.generate("one")
            client.generate("two")
        usage = client.usage()
        self.assertEqual((usage["calls"], usage["errors"]), (2, 0))
        self.assertEqual((usage["tokens_in"], usage["tokens_out"]), (12, 5))

    def test_fingerprint_is_stable_and_model_sensitive(self):
        one = LLMClient(model="a").fingerprint()
        self.assertEqual(one, LLMClient(model="a").fingerprint())
        self.assertNotEqual(one, LLMClient(model="b").fingerprint())
        self.assertTrue(one.startswith("sha256:"))
        self.assertNotEqual(EmbeddingClient(model="a").fingerprint(), EmbeddingClient(model="b").fingerprint())

    def test_embedding_call_is_accounted(self):
        with patch.object(llm, "embed", return_value=[[0.1], [0.2]]) as embed:
            client = EmbeddingClient(model="bge-m3")
            self.assertEqual(client.embed(["a", "bb"]), [[0.1], [0.2]])
        self.assertEqual(embed.call_args.args[0], ["a", "bb"])
        self.assertEqual(client.calls[0].items, 2)
        self.assertEqual(client.usage()["items"], 2)


class LegacyAdapterTests(unittest.TestCase):
    def test_each_adapter_forwards_its_original_method_name(self):
        for name, method in legacy.LEGACY_METHODS.items():
            adapter = registry.build("method", name)
            self.assertEqual(adapter.method, method)
            with patch.object(pipeline, "answer", return_value={"answer": "x"}) as answer:
                self.assertEqual(adapter.answer("conv-26", "q", k=4), {"answer": "x"})
            answer.assert_called_once_with("conv-26", "q", method, k=4, as_of=None, expand=8)

    def test_constructor_parameters_are_defaults(self):
        adapter = registry.build("method", "legacy_dynamic", {"k": 3, "expand": 2})
        with patch.object(pipeline, "answer", return_value={}) as answer:
            adapter.answer("conv-26", "q")
        answer.assert_called_once_with("conv-26", "q", "dynamic", k=3, as_of=None, expand=2)

    def test_unknown_parameters_are_rejected(self):
        with self.assertRaises(TypeError):
            registry.build("method", "legacy_dynamic", {"nope": 1})


class RuntimeTests(unittest.TestCase):
    def test_runtime_binds_config_clients_and_manifest(self):
        machine = runtime.Runtime.load(REFERENCE_B0)
        self.assertEqual(machine.method, "legacy_dynamic")
        self.assertEqual(machine.adapter().method, "dynamic")
        built = machine.manifest(run_id="r-test")
        self.assertEqual(built.config_hash, machine.config.config_hash)
        self.assertEqual(built.seed, 13)
        self.assertIn("extract", built.prompts)

    def test_runtime_forwards_explicit_parameters_only(self):
        machine = runtime.Runtime.load(REFERENCE_B0)
        with patch.object(pipeline, "answer", return_value={"answer": "x"}) as answer:
            machine.answer("conv-26", "q", k=5, as_of="2023-05-08", expand=2)
        answer.assert_called_once_with("conv-26", "q", "dynamic", k=5, as_of="2023-05-08", expand=2)

    def test_runtime_rejects_invalid_configuration(self):
        with self.assertRaises(lab_config.ConfigError):
            runtime.Runtime({"graph": {"repr": {"impl": "none"}, "retrieval": {"impl": "slot_expand"}}})

    def test_runtime_unknown_method_lists_available(self):
        machine = runtime.Runtime.load(REFERENCE_B0)
        with self.assertRaises(registry.UnknownImplementation) as caught:
            machine.answer("conv-26", "q", method="legacy_missing")
        self.assertIn("legacy_vector", str(caught.exception))


class LegacyParityTests(unittest.TestCase):
    """A1 acceptance: 10 questions must produce byte-identical results to the old code."""

    @classmethod
    def setUpClass(cls):
        cls.sample = dataset.store().get("conv-26")
        cls.turns, cls.facts = memory.build(cls.sample)
        cls.questions = [question for _, question in evaluation.answerable(cls.sample.get("qa", []))][:10]
        if len(cls.questions) != 10:
            raise unittest.SkipTest("conv-26 does not provide 10 answerable questions")

    def _replies(self, method, question):
        if method == "dynamic":
            states = {"memories": [{"id": turn["memory_id"], "state": "ACTIVE"} for turn in self.turns[:3]],
                      "relations": []}
            return [states, {"answer": question["answer"]}]
        return [{"answer": question["answer"]}]

    def _old(self, method, question):
        selected = list(self.turns[:3])
        with patch.object(memory, "build", return_value=(self.turns, self.facts)), \
                patch.object(retrieval, "hybrid", return_value=selected), \
                patch.object(retrieval, "vector", return_value=selected), \
                patch.object(llm, "generate", side_effect=self._replies(method, question)):
            return pipeline.answer("conv-26", question["question"], method, k=3)

    def _new(self, method, question):
        adapter = registry.build("method", f"legacy_{method}")
        selected = list(self.turns[:3])
        with patch.object(memory, "build", return_value=(self.turns, self.facts)), \
                patch.object(retrieval, "hybrid", return_value=selected), \
                patch.object(retrieval, "vector", return_value=selected), \
                patch.object(llm, "generate", side_effect=self._replies(method, question)):
            return adapter.answer("conv-26", question["question"], k=3)

    @staticmethod
    def _comparable(output):
        payload = {key: value for key, value in output.items() if key != "steps"}
        payload["steps"] = [(step["name"], step["detail"]) for step in output.get("steps", [])]
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)

    @staticmethod
    def _metrics(output, question):
        return {
            "answer": output["answer"],
            "f1": evaluation.answer_f1(output["answer"], question["answer"], question["category"]),
            "recall": evaluation.recall(evaluation.evidence_turns(question), output.get("retrieved_turns", [])),
            "valid_memory_ids": output.get("valid_memory_ids"),
            "states": {item["id"]: item["state"] for item in output.get("memories", [])},
        }

    def _assert_parity(self, method):
        f1_scores, recalls, states = [], [], {}
        for question in self.questions:
            old, new = self._old(method, question), self._new(method, question)
            self.assertEqual(self._comparable(old), self._comparable(new),
                             msg=f"{method}: output differs on {question['question']!r}")
            old_metrics, new_metrics = self._metrics(old, question), self._metrics(new, question)
            self.assertEqual(old_metrics, new_metrics)
            f1_scores.append(old_metrics["f1"])
            if old_metrics["recall"] is not None:
                recalls.append(old_metrics["recall"])
            states.update(old_metrics["states"] or {})
        self.assertEqual(len(f1_scores), 10)
        return evaluation.mean(f1_scores), evaluation.mean(recalls), len(states)

    def test_legacy_full_matches_the_original_pipeline(self):
        self._assert_parity("full")

    def test_legacy_vector_matches_the_original_pipeline(self):
        self._assert_parity("vector")

    def test_legacy_hybrid_matches_the_original_pipeline(self):
        self._assert_parity("hybrid")

    def test_legacy_dynamic_matches_the_original_pipeline(self):
        f1, recall, state_count = self._assert_parity("dynamic")
        self.assertEqual(f1, 1.0)  # answers are the gold answers by construction
        self.assertIsNotNone(recall)
        self.assertGreater(state_count, 0)


if __name__ == "__main__":
    unittest.main()
