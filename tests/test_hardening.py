"""Hardening tests for the S1/S2 gaps found before S3.

Run:
    python -m unittest tests.test_hardening -v
"""
import unittest
from datetime import datetime
from unittest.mock import patch

from memlab import cache, config, guards, legacy, model
from memlab.llm import LLMClient
from memwb import llm as legacy_llm

REFERENCE_B0 = config.ROOT / "configs" / "reference-b0.json"
REFERENCE_R0 = config.ROOT / "configs" / "reference-r0.json"


class GuardTests(unittest.TestCase):
    def test_b0_is_allowed_and_r0_is_rejected(self):
        b0 = config.RunConfig.load(REFERENCE_B0)
        r0 = config.RunConfig.load(REFERENCE_R0)
        guards.require_runnable(b0)  # must not raise
        with self.assertRaises(guards.UnimplementedPipeline):
            guards.require_runnable(r0)

    def test_explicit_legacy_method_is_allowed(self):
        data = config.RunConfig.load(REFERENCE_R0).to_dict()
        data["method"] = {"impl": "legacy_dynamic"}
        guards.require_runnable(config.RunConfig.from_dict(data))

    def test_error_names_the_module_that_is_not_implemented(self):
        r0 = config.RunConfig.load(REFERENCE_R0)
        with self.assertRaises(guards.UnimplementedPipeline) as caught:
            guards.require_runnable(r0)
        message = str(caught.exception)
        self.assertIn("schema.impl=meta_schema", message)
        self.assertIn("legacy_*", message)


class LLMRequestTests(unittest.TestCase):
    def test_client_overrides_reach_the_request_body(self):
        seen = {}

        def fake_post(path, body, **kwargs):
            seen.update(body)
            return {"response": "ok", "prompt_eval_count": 1, "eval_count": 1}

        with patch.object(legacy_llm, "post", side_effect=fake_post):
            LLMClient(model="test-model", temperature=0.7, context=8192,
                      options={"num_gpu": 0}).generate("q")
        self.assertEqual(seen["options"]["temperature"], 0.7)
        self.assertEqual(seen["options"]["num_ctx"], 8192)
        self.assertEqual(seen["options"]["num_gpu"], 0)

    def test_default_generation_keeps_legacy_options(self):
        seen = {}

        def fake_post(path, body, **kwargs):
            seen.update(body)
            return {"response": "ok", "prompt_eval_count": 1, "eval_count": 1}

        with patch.object(legacy_llm, "post", side_effect=fake_post):
            LLMClient(model="test-model").generate("q")
        self.assertEqual(seen["options"]["temperature"], 0)
        self.assertIn("num_ctx", seen["options"])


class CacheVersionTests(unittest.TestCase):
    def test_explicit_code_versions_change_the_key(self):
        one = cache.ArtifactCache("/tmp/memlab-cache-test", code_version="abc123")
        two = cache.ArtifactCache("/tmp/memlab-cache-test", code_version="def456")
        self.assertNotEqual(one.key("stage", {"x": 1}), two.key("stage", {"x": 1}))

    def test_make_key_treats_code_version_as_content(self):
        self.assertNotEqual(
            cache.make_key("stage", {"x": 1}, code_version="a"),
            cache.make_key("stage", {"x": 1}, code_version="b"),
        )

    def test_default_cache_records_a_code_version(self):
        store = cache.ArtifactCache("/tmp/memlab-cache-test")
        self.assertTrue(store.code_version)
        self.assertEqual(store.key("stage", {"x": 1}), store.key("stage", {"x": 1}))


class ValidityTests(unittest.TestCase):
    @staticmethod
    def fact(**overrides):
        base = {
            "memory_id": "f1", "content": "A · job: x", "entity": "A", "attribute": "job",
            "value": "x", "state": "HISTORICAL", "session_time": "2023-01-01T00:00",
            "resolved_date": "2022-12-01", "relations": [], "source": {"turn": "D1:1"},
        }
        base.update(overrides)
        return base

    def test_historical_without_invalidator_is_unknown_not_open_ended(self):
        unit = model.from_fact(self.fact())
        self.assertIsNone(unit.valid_interval.end)
        self.assertFalse(model.validity_known(unit))
        self.assertIsNone(model.is_valid_at(unit, datetime(2024, 1, 1)))

    def test_historical_with_invalidator_is_known(self):
        later = self.fact(memory_id="f2", resolved_date="2023-03-01", state="ACTIVE")
        earlier = self.fact(relations=[{"type": "SUPERSEDE", "direction": "to", "memory_id": "f2"}])
        by_id = {"f1": earlier, "f2": later}
        unit = model.from_fact(earlier, facts_by_id=by_id)
        self.assertTrue(model.validity_known(unit))
        self.assertEqual(unit.valid_interval.end, datetime(2023, 3, 1))
        self.assertTrue(model.is_valid_at(unit, datetime(2023, 1, 1)))
        self.assertFalse(model.is_valid_at(unit, datetime(2023, 6, 1)))

    def test_active_fact_is_known(self):
        unit = model.from_fact(self.fact(state="ACTIVE"))
        self.assertTrue(model.validity_known(unit))
        self.assertTrue(model.is_valid_at(unit, datetime(2024, 1, 1)))


if __name__ == "__main__":
    unittest.main()
