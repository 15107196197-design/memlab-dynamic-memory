"""W1 Web API tests: additive /api/v2, no browser/LLM required."""
import json
import time
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

    def test_axes_are_registry_backed(self):
        data = webapp.get("/api/v2/config/axes")
        by_id = {axis["id"]: axis for axis in data["axes"]}
        self.assertIn("schema", by_id)
        self.assertIn("fusion", by_id)
        self.assertIn("logic.state_resolver", by_id)
        self.assertIn("meta_schema", by_id["schema"]["available"])

    def test_axes_are_grouped_by_six_modules(self):
        data = webapp.get("/api/v2/config/axes")
        self.assertEqual([m["id"] for m in data["modules"]], ["W", "S", "R", "M", "U", "K"])
        modules = {m["id"]: m for m in data["modules"]}
        self.assertEqual([a["id"] for a in modules["W"]["axes"]], ["schema", "write.resolver", "write.auditor"])
        self.assertIn("retrieval.channels", [a["id"] for a in modules["R"]["axes"]])
        self.assertEqual(modules["K"]["axes"], [])
        channels = next(a for a in modules["R"]["axes"] if a["id"] == "retrieval.channels")
        self.assertIn("graph", channels["available"])

    def test_hardware_limits_are_explicit_and_distinct_from_unimplemented(self):
        data = webapp.get("/api/v2/config/axes")
        hardware = data["hardware"]
        self.assertEqual(hardware["local_llm_scale"]["status"], "hardware_blocked")
        self.assertTrue(hardware["local_llm_scale"]["design_retained"])
        self.assertIn("API", hardware["local_llm_scale"]["alternative"])
        by_id = {axis["id"]: axis for axis in data["axes"]}
        self.assertEqual(by_id["rerank"]["status"], "hardware_limited")
        self.assertIn("cross_encoder", by_id["rerank"]["option_status"])
        modules = {m["id"]: m for m in data["modules"]}
        self.assertEqual(modules["M"]["hardware_status"], "hardware_limited")
        self.assertIn("GPU", modules["M"]["hardware_note"])
        self.assertIn("hardware_blocked", data["status_legend"])

    def test_memory_kind_filter_and_structured_fields(self):
        facts = webapp.get("/api/v2/memories", {"sample": ["conv-26"], "kind": ["fact"], "page_size": ["5"]})
        self.assertGreater(facts["total"], 0)
        self.assertGreater(facts["counts"]["event"], 0)
        first = facts["memories"][0]
        for key in ("entity", "attribute", "value", "event", "time_expression", "display_kind"):
            self.assertIn(key, first)
        events = webapp.get("/api/v2/memories", {"sample": ["conv-26"], "kind": ["event"], "page_size": ["5"]})
        self.assertGreater(events["total"], 0)
        self.assertTrue(all(m["event"] for m in events["memories"]))

    def test_graph_endpoint_returns_nodes_and_fact_edges(self):
        graph = webapp.get("/api/v2/graph", {"sample": ["conv-26"], "limit": ["60"]})
        self.assertGreater(len(graph["nodes"]), 0)
        self.assertGreater(len(graph["edges"]), 0)
        ids = {node["id"] for node in graph["nodes"]}
        self.assertTrue(all(edge["source"] in ids and edge["target"] in ids for edge in graph["edges"]))
        self.assertGreater(graph["total_relations"], 0)
        self.assertTrue(any(node["kind"] in ("fact", "event") for node in graph["nodes"]))

    def test_system_reports_hardware_boundary(self):
        data = webapp.get("/api/v2/system")
        self.assertEqual(data["hardware"]["machine"], "MacBook Air M2 (2022)")
        self.assertTrue(any("硬件受限" in gap for gap in data["gaps"]))

    def test_async_job_completes(self):
        job = webapp.post("/api/v2/jobs", {
            "sample": "conv-26", "preset": "B0",
            "question": "What did Caroline do last Friday?", "offline": True,
        })
        deadline = time.time() + 20
        while time.time() < deadline:
            state = webapp.get(f"/api/v2/jobs/{job['job_id']}")
            if state["status"] in ("done", "error"):
                break
            time.sleep(0.1)
        self.assertEqual(state["status"], "done", state.get("error"))
        self.assertIn("run_id", state["result"])

    def test_report_has_four_sections_and_is_published(self):
        base = webapp.post("/api/v2/runs", {"sample": "conv-26", "preset": "B0",
                                             "question": "What did Caroline do last Friday?", "offline": True})
        cand = webapp.post("/api/v2/runs", {"sample": "conv-26", "preset": "R0",
                                             "question": "What did Caroline do last Friday?", "offline": True})
        report = webapp.post("/api/v2/experiments/w1-test/report", {"run_ids": [base["run_id"], cand["run_id"]]})
        self.assertEqual(report["schema"], "memlab/experiment-report@1")
        for key in ("results", "comparisons", "analysis", "conclusion"):
            self.assertIn(key, report)
        self.assertEqual(report["conclusion"]["status"], "inconclusive")
        self.assertTrue(report["web"]["published"])
        self.assertEqual(webapp.get("/api/v2/experiments/w1-test/report")["experiment_id"], "w1-test")
        (Path(__file__).resolve().parents[1] / "reports" / "experiments" / "w1-test.json").unlink(missing_ok=True)

    def test_batch_run_reports_f1_and_recall(self):
        out = webapp.post("/api/v2/runs", {
            "sample": "conv-26", "preset": "B0", "batch": True,
            "questions": 6, "seed": 13, "offline": True,
        })
        self.assertEqual(out["kind"], "batch")
        self.assertEqual(out["questions"], 6)
        self.assertIn("answer_f1", out["metrics"])
        self.assertIn("evidence_recall", out["metrics"])
        self.assertEqual(len(out["rows"]), 6)
        self.assertTrue(out["by_category"])

    def test_memory_facets_and_timeline(self):
        data = webapp.get("/api/v2/memories", {"sample": ["conv-26"], "page_size": ["1"]})
        self.assertEqual(data["counts"]["fact"], 335)
        self.assertEqual(data["counts"]["event"], 146)
        self.assertEqual(data["counts"]["turn"], 419)
        self.assertEqual(data["facets"]["status"]["CONFLICT"], 0)
        self.assertGreater(data["facets"]["entities"][0]["count"], 0)
        facts = webapp.get("/api/v2/memories", {"sample": ["conv-26"], "type": ["fact"], "page_size": ["1"]})
        self.assertEqual(facts["total"], 189)
        timeline = webapp.get("/api/v2/timeline", {"sample": ["conv-26"]})
        self.assertEqual(timeline["axis"], "t_ingest")
        self.assertGreater(timeline["fact_count"], 0)
        self.assertIn("groups", timeline)

    def test_semantic_graph_has_entity_slot_fact_and_typed_edges(self):
        graph = webapp.get("/api/v2/graph", {"sample": ["conv-26"], "mode": ["changed"]})
        self.assertEqual({n["kind"] for n in graph["nodes"]}, {"entity", "slot", "fact"})
        self.assertIn("member", {e["type"] for e in graph["edges"]})
        self.assertTrue({e["type"] for e in graph["edges"]} & {"RETAIN", "UPDATE", "SUPERSEDE", "CONFLICT"})
        self.assertLessEqual(graph["stats"]["facts_shown"], 400)
        self.assertGreater(graph["stats"]["nodes"], 0)

    def test_experiment_catalog_covers_modules_and_stages(self):
        data = webapp.get("/api/v2/experiments/plan")
        self.assertGreaterEqual(data["count"], 20)
        modules = {item["module"] for item in data["items"]}
        for module in ("W", "S", "R", "M", "U", "K", "E2", "E3", "E4", "E5"):
            self.assertIn(module, modules)
        # 2026-11-09 schema: offline evidence is partial+grade=offline;
        # blocked is split into blocked_on_code / blocked_on_hardware.
        self.assertGreater(data["status_counts"].get("partial", 0), 0)
        self.assertGreater(data["status_counts"].get("blocked_on_code", 0), 0)
        self.assertGreater(data["status_counts"].get("blocked_on_hardware", 0), 0)
        flags = data.get("status_flag_counts", {})
        self.assertGreater(flags.get("no_op", 0) + flags.get("not_wired", 0), 0)

    def test_evaluation_archive_is_available(self):
        data = webapp.get("/api/v2/evaluation")
        self.assertTrue(data["available"])
        self.assertIn("full", data["qa"]["test"]["summary"])
        self.assertIn("vector", data["qa"]["test"]["summary"])
        self.assertIn("test", data["split"])

    def test_six_conversation_export_bundle(self):
        bundle = webapp.get("/api/v2/export/all", {"schema": ["2"]})
        self.assertEqual(bundle["schema"], "memlab/web-export-bundle@1")
        self.assertEqual(len(bundle["documents"]), 6)
        for sample_id in ("conv-26", "conv-30", "conv-43", "conv-44", "conv-41", "conv-42"):
            self.assertIn(sample_id, bundle["documents"])

    def test_final_w3_report_has_four_tabs_and_c_artifacts(self):
        report = webapp.get("/api/v2/experiments/final-w3-test-offline/report")
        for key in ("results", "comparisons", "analysis", "conclusion"):
            self.assertIn(key, report)
        self.assertEqual(report["dataset"]["split"], "test")
        self.assertTrue(report["dataset"]["test_only"])
        artifacts = webapp.get("/api/v2/artifacts")["artifacts"]
        self.assertTrue(all(artifacts[key]["available"] for key in ("state_accuracy", "e1_adoption", "e3_offline", "planner_k")))

    def test_c_artifacts_and_project_reports_are_separate(self):
        art = webapp.get("/api/v2/artifacts")
        for key in ("state_accuracy", "e1_adoption", "e3_offline", "planner_k"):
            self.assertTrue(art["artifacts"][key]["available"], key)
        ev = webapp.get("/api/v2/evaluation")
        self.assertIn("qa", ev)
        ids = {r["experiment_id"] for r in ev["project_reports"]}
        self.assertIn("final-w3-test-offline", ids)
        final = next(r for r in ev["project_reports"] if r["experiment_id"] == "final-w3-test-offline")
        self.assertIn("baseline_metrics", final["results"])

    def test_system_exposes_provenance(self):
        data = webapp.get("/api/v2/system")
        self.assertIn("course", data["provenance"])
        self.assertIn("inherited", data["provenance"])
        self.assertIn("this_project", data["provenance"])
        self.assertTrue(any("final-w3" in item["path"] for item in data["provenance"]["this_project"]["items"]))

    def test_static_shell_has_v2_navigation(self):
        html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
        for route in ("#/memories", "#/ask2", "#/lab", "#/graph2", "#/evaluation2", "#/system"):
            self.assertIn(route, html)
        self.assertIn("#/home", html)
        self.assertIn("/v2.js", html)


if __name__ == "__main__":
    unittest.main()
