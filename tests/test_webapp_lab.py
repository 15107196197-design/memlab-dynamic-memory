"""W-API tests: LoCoMo question catalogue, run-to-report pipeline and friendly 502s."""
import json
import os
import time
import unittest
from pathlib import Path

from memlab import webapp

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs" / "web"
REPORTS_DIR = ROOT / "reports" / "experiments"


def _synthetic_batch(run_id: str, *, preset: str, f1_shift: float, questions: int = 12) -> dict:
    rows = []
    for index in range(questions):
        f1 = round(0.10 + (0.02 if index % 2 else 0.0) + f1_shift, 4)
        rows.append({
            "qid": f"conv-26:{index}",
            "category": str((index % 4) + 1),
            "question": f"question {index}",
            "gold": f"gold {index}",
            "prediction": f"prediction {index}",
            "answer_f1": f1,
            "evidence_recall": round(0.40 + f1_shift, 4),
            "tokens": 100 + index,
            "latency_ms": 1.0 + index / 10,
            "candidates": 10,
            "refused": 0,
        })
    return {
        "kind": "batch",
        "run_id": run_id,
        "sample": "conv-26",
        "preset": preset,
        "config_hash": f"sha256:{preset.lower()}synthetic",
        "offline": True,
        "seed": 13,
        "questions": questions,
        "metrics": {
            "answer_f1": round(sum(row["answer_f1"] for row in rows) / questions, 4),
            "evidence_recall": round(sum(row["evidence_recall"] for row in rows) / questions, 4),
            "state_accuracy": None,
            "tokens": round(sum(row["tokens"] for row in rows) / questions, 2),
            "p95_latency_ms": 2.0,
            "error_rate": 0.0,
            "questions": questions,
        },
        "rows": rows,
        "by_category": [],
        "stage_waterfall": [{"stage": "retrieve", "ms": 1.0}, {"stage": "merge", "ms": 0.5}],
        "model": {"llm": "offline-extractive", "embedding": "offline-hash", "offline": True},
        "trace": [],
    }


class WebAppLabTests(unittest.TestCase):
    def setUp(self):
        self.added_runs = []
        self.added_reports = []

    def tearDown(self):
        for run_id in self.added_runs:
            (RUNS_DIR / f"{run_id}.json").unlink(missing_ok=True)
        for report_id in self.added_reports:
            (REPORTS_DIR / f"{report_id}.json").unlink(missing_ok=True)

    def _write_run(self, payload: dict) -> str:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        run_id = payload["run_id"]
        (RUNS_DIR / f"{run_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.added_runs.append(run_id)
        return run_id

    def test_questions_endpoint_fields_filter_and_limit(self):
        data = webapp.get("/api/v2/questions", {"sample": ["conv-26"], "limit": ["5"]})
        self.assertEqual(data["sample"], "conv-26")
        self.assertEqual(data["count"], 5)
        self.assertGreater(data["total"], 0)
        first = data["questions"][0]
        for key in ("qid", "index", "question", "answer", "category", "category_label", "evidence"):
            self.assertIn(key, first)
        self.assertEqual(first["qid"], f"conv-26-q{first['index']}")
        self.assertIsInstance(first["evidence"], list)

        filtered = webapp.get("/api/v2/questions", {
            "sample": ["conv-26"], "category": ["2"], "limit": ["8"]})
        self.assertGreater(filtered["count"], 0)
        for question in filtered["questions"]:
            self.assertEqual(question["category"], 2)
            self.assertEqual(question["category_label"], "时间")

    def test_from_runs_writes_four_section_report(self):
        suffix = f"{os.getpid()}-{time.time_ns()}"
        baseline_id = self._write_run(_synthetic_batch(
            f"unittest-base-{suffix}", preset="B0", f1_shift=0.0))
        candidate_id = self._write_run(_synthetic_batch(
            f"unittest-cand-{suffix}", preset="R0", f1_shift=0.05))
        experiment_id = f"lab-unittest-{suffix}"
        out = webapp.post("/api/v2/reports/from-runs", {
            "baseline_run_id": baseline_id,
            "candidate_run_id": candidate_id,
            "experiment_id": experiment_id,
            "module": "M",
            "stage": "E1.1",
            "title": "synthetic B0 vs R0",
        })
        self.added_reports.append(out["report_id"])
        report = out["report"]
        self.assertEqual(report["schema"], "memlab/experiment-report@1")
        self.assertEqual(out["web_path"], f"#/experiments/{out['report_id']}")
        for key in ("results", "comparisons", "analysis", "conclusion"):
            self.assertIn(key, report)
        self.assertEqual(len(report["results"]["runs"]), 2)
        self.assertEqual([run["role"] for run in report["results"]["runs"]],
                         ["baseline", "candidate"])
        self.assertTrue(report["comparisons"])
        f1 = next(item for item in report["comparisons"] if item["metric"] == "answer_f1")
        self.assertTrue(f1["paired"])
        self.assertEqual(f1["pairs"], 12)
        self.assertAlmostEqual(f1["delta"], 0.05, places=4)
        self.assertIn(report["conclusion"]["status"], ("partial", "supported", "not_supported"))
        self.assertIn("no bootstrap CI", " ".join(report["conclusion"]["limitations"]))
        self.assertIn("metadata", report)
        self.assertTrue(report["metadata"]["baseline"]["config_hash"])
        self.assertTrue(report["metadata"]["candidate"]["config_hash"])
        self.assertTrue((REPORTS_DIR / f"{out['report_id']}.json").is_file())
        self.assertEqual(webapp.get(f"/api/v2/experiments/{out['report_id']}/report")["experiment_id"],
                         out["report_id"])

    def test_from_runs_missing_run_is_404_and_does_not_write_empty_report(self):
        experiment_id = f"lab-missing-{os.getpid()}-{time.time_ns()}"
        for baseline, candidate in (
            (f"missing-base-{time.time_ns()}", f"missing-cand-{time.time_ns()}"),
            (f"missing-base-{time.time_ns()}", "definitely-not-a-run"),
        ):
            with self.assertRaises(webapp.WebError) as caught:
                webapp.post("/api/v2/reports/from-runs", {
                    "baseline_run_id": baseline,
                    "candidate_run_id": candidate,
                    "experiment_id": experiment_id,
                })
            self.assertEqual(caught.exception.status, 404)
        self.assertFalse((REPORTS_DIR / f"{experiment_id}.json").exists())

    def test_offline_run_uses_extractive_model_and_offline_flag(self):
        out = webapp.post("/api/v2/runs", {
            "sample": "conv-26", "preset": "B0",
            "question": "What did Caroline do last Friday?",
            "offline": True,
        })
        self.added_runs.append(out["run_id"])
        self.assertTrue(out["offline"])
        self.assertTrue(out["model"]["offline"])
        self.assertEqual(out["model"]["llm"], "offline-extractive")

    def test_connection_refused_maps_to_model_unavailable_payload(self):
        original = webapp._run_module

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError(61, "Connection refused")

        webapp._run_module = refuse
        try:
            with self.assertRaises(webapp.ModelUnavailableError) as caught:
                webapp.post("/api/v2/runs", {
                    "sample": "conv-26", "question": "q", "offline": False})
        finally:
            webapp._run_module = original
        payload = caught.exception.as_payload()
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual(payload["code"], "model_unavailable")
        self.assertIn("本地模型不可用", payload["message"])
        self.assertNotIn("Errno 61", payload["message"])
        self.assertTrue(payload["hint"])


if __name__ == "__main__":
    unittest.main()
