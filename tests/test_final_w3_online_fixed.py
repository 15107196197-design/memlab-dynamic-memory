"""Guards for the post-hoc R0-fixed report and the Evaluation page wiring."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from memlab import webapp

ROOT = Path(__file__).resolve().parents[1]


class FinalW3OnlineFixedReportTests(unittest.TestCase):
    def test_both_fixed_copies_carry_refusal_metrics_and_analysis(self):
        paths = [
            ROOT / "eval" / "archive" / "final-w3-test-online-fixed.json",
            ROOT / "reports" / "experiments" / "final-w3-test-online-fixed.json",
        ]
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        self.assertEqual(reports[0], reports[1])
        for report in reports:
            for block in ("metrics", "baseline_metrics"):
                for key in ("refused_rate", "answered_questions", "answered_f1"):
                    self.assertIn(key, report["results"][block], (block, key))
            diagnosis = report["analysis"]["diagnosis"]
            for key in (
                "dev_before", "dev_after", "root_cause", "time_context", "rerank",
                "test_reused", "test_questions_per_config", "before_questions_per_config",
            ):
                self.assertIn(key, diagnosis)
            self.assertEqual(diagnosis["test_questions_per_config"], 20)
            self.assertEqual(diagnosis["before_questions_per_config"], 80)
            self.assertTrue(diagnosis["test_reused"])
            before_after = report["analysis"]["before_after"]
            self.assertEqual(set(before_after), {"dev", "test"})
            for split in ("dev", "test"):
                self.assertIn("before", before_after[split])
                self.assertIn("after", before_after[split])
            text = json.dumps(report["conclusion"], ensure_ascii=False)
            for needle in ("post-hoc", "refused", "80", "20", "配对"):
                self.assertIn(needle, text)

    def test_before_report_carries_derived_refusal_metrics(self):
        before = json.loads((ROOT / "reports" / "experiments" / "final-w3-test-online.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(before["results"]["metrics"]["refused_rate"], 0.5375)
        self.assertAlmostEqual(before["results"]["metrics"]["answered_f1"], 0.278)
        self.assertAlmostEqual(before["results"]["baseline_metrics"]["refused_rate"], 0.3875)
        self.assertAlmostEqual(before["results"]["baseline_metrics"]["answered_f1"], 0.2728)

    def test_report_api_exposes_fixed_and_before_fix(self):
        fixed = webapp.get("/api/v2/experiments/final-w3-test-online-fixed/report")
        self.assertAlmostEqual(fixed["results"]["metrics"]["refused_rate"], 0.3)
        self.assertAlmostEqual(fixed["results"]["metrics"]["answered_f1"], 0.2924)
        self.assertIn("diagnosis", fixed["analysis"])
        before = webapp.get("/api/v2/experiments/final-w3-test-online-before-fix/report")
        self.assertAlmostEqual(before["results"]["metrics"]["refused_rate"], 0.5375)
        self.assertAlmostEqual(before["results"]["metrics"]["answered_f1"], 0.278)

    def test_evaluation_page_wires_online_before_fixed_and_diagnosis(self):
        js = (ROOT / "web" / "v2.js").read_text(encoding="utf-8")
        for needle in (
            "final-w3-test-online-before-fix",
            "final-w3-test-online-fixed",
            "final-w3-test-offline",
            "answered F1",
            "refused",
            "为什么之前差 / dev 诊断",
            "filter=none + rerank=none",
            "post-hoc",
            "不能做 before-vs-fixed 的配对显著性结论",
            "Judge:",
            "state_accuracy",
        ):
            self.assertTrue(needle in js, f"web/v2.js is missing {needle!r}")


if __name__ == "__main__":
    unittest.main()
