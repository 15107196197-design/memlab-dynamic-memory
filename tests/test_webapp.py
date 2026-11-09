"""W1 Web API tests: additive /api/v2, no browser/LLM required."""
import json
import unittest
from pathlib import Path

from memlab import webapp


class WebAppTests(unittest.TestCase):
    def test_course_is_four_development_plus_two_test(self):
        data = webapp.get("/api/v2/course")
        self.assertEqual(data["count"], 6)
        self.assertEqual([s["id"] for s in data["samples"] if s["split"] == "test"], ["conv-41", "conv-42"])
        self.assertEqual(sum(1 for s in data["samples"] if s["split"] == "development"), 4)

    def test_memory_list_and_detail_have_v2_fields_and_evidence(self):
        page = webapp.get("/api/v2/memories", {"sample": ["conv-26"], "page_size": ["2"]})
        self.assertEqual(page["sample"], "conv-26")
        self.assertGreater(page["total"], 0)
        first = page["memories"][0]
        for key in ("memory_id", "kind", "text", "t_event", "t_ingest", "source_turn", "evidence_count"):
            self.assertIn(key, first)
        detail = webapp.get(f"/api/v2/memories/{first['memory_id']}", {"sample": ["conv-26"]})
        self.assertEqual(detail["memory"]["memory_id"], first["memory_id"])
        self.assertIn("structured", detail["memory"])
        self.assertTrue(detail["source_turns"])

    def test_export_v2_and_v1(self):
        v2 = webapp.get("/api/v2/export", {"sample": ["conv-26"], "schema": ["2"]})
        self.assertEqual(v2["schema"], "dynamic-memory-workbench/memory-export@2")
        self.assertIn("memories", v2)
        self.assertIn("relations", v2)
        v1 = webapp.get("/api/v2/export", {"sample": ["conv-26"], "schema": ["1"]})
        self.assertNotEqual(v1.get("schema"), v2["schema"])

    def test_config_validate_presets(self):
        b0 = webapp.post("/api/v2/config/validate", {"preset": "B0"})
        self.assertTrue(b0["valid"])
        self.assertTrue(b0["runnable"])
        self.assertTrue(b0["config_hash"])
        bad = webapp.post("/api/v2/config/validate", {"config": {"schema": {"impl": "does_not_exist"}}})
        self.assertFalse(bad["valid"] or bad["runnable"])
        self.assertTrue(bad["problems"])

    def test_offline_module_run_has_state_and_trace(self):
        out = webapp.post("/api/v2/runs", {
            "sample": "conv-26", "preset": "B0",
            "question": "What did Caroline do last Friday?",
            "offline": True,
        })
        self.assertEqual(out["mode"], "module")
        self.assertTrue(out["offline"])
        self.assertIn("answer", out["answer"])
        self.assertIn("valid_ids", out["state"])
        self.assertGreater(out["latency_ms"], 0)
        self.assertTrue(out["trace"])
        self.assertGreater(len(out["candidates"]), 0)

    def test_static_shell_has_v2_navigation(self):
        html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("#/memories", html)
        self.assertIn("#/ask2", html)
        self.assertIn("#/lab", html)
        self.assertIn("/v2.js", html)


if __name__ == "__main__":
    unittest.main()
