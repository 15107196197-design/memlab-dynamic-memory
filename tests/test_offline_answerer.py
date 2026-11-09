"""Regression tests for the opt-in offline answerer switch.

The archived W3 offline report (B0 F1 0.0354 / R0 F1 0.0054) was produced by the
prompt-driven extractive path in ``OfflineLLM.generate``.  U5 wired every offline
run to the richer ``offline_qa`` demo extractor without changing the model
fingerprint, which made the archived numbers unreproducible.  These tests pin the
default to extractive_v1, the switch to offline_qa, and the report metrics.

The report's R0 config hash (``sha256:b86df9...``) belongs to
``reference-r0-original.json``; ``reference-r0.json`` was later frozen as
R0-fixed for the online report, so it is deliberately not used here.
"""
from __future__ import annotations

import hashlib
import statistics
import tempfile
import unittest
from pathlib import Path

from memlab import cache as lab_cache
from memlab import config as lab_config
from memlab import merge, webapp
from memlab.e2e import E2EPipeline
from memlab.experiments import compiler, executor
from memwb import evaluation

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_B0 = ROOT / "configs" / "reference-b0.json"
REFERENCE_R0_REPORT = ROOT / "configs" / "reference-r0-original.json"
TEST_SAMPLES = ("conv-41", "conv-42")
TEST_SEEDS = (13, 17)
QUESTIONS_PER_RUN = 20


def fingerprint(version: str) -> str:
    return "sha256:" + hashlib.sha256(version.encode("utf-8")).hexdigest()


def plan_for(config: lab_config.RunConfig, sample_id: str):
    data = config.to_dict()
    return compiler.RunPlan(
        run_id=f"test-offline-{config.preset}-{sample_id}",
        spec_id="OFFLINE-REPRO",
        design="single_config",
        config=data,
        requested_config=data,
        effective_config=data,
        config_hash=config.config_hash,
        environment=data.get("environment") or {},
        dataset={"samples": [sample_id], "question_limit": QUESTIONS_PER_RUN},
        factors={},
    )


def measure_offline(config: lab_config.RunConfig, cache: lab_cache.ArtifactCache):
    """Run the same 80 questions/config as the archived final-w3 offline report."""
    rows: list[dict[str, float | None]] = []
    fingerprints: set[str] = set()
    for sample_id in TEST_SAMPLES:
        plan = plan_for(config, sample_id)
        ctx = executor.build_context(plan, sample_id, offline=True, cache=cache)
        fingerprints.add(ctx.llm.fingerprint())
        pipeline = E2EPipeline(ctx)
        for seed in TEST_SEEDS:
            for _index, qa in webapp._select_questions(sample_id, QUESTIONS_PER_RUN, seed):
                gold = evaluation.evidence_turns(qa)
                result = pipeline.run(str(qa.get("question") or ""), k=15, gold_turns=gold)
                retrieved: set[str] = set()
                for unit in result.merge.units:
                    retrieved |= merge.unit_turns(unit)
                rows.append({
                    "answer_f1": evaluation.answer_f1(
                        result.answer.answer, qa.get("answer"), qa.get("category")),
                    "evidence_recall": evaluation.recall(gold, sorted(retrieved)),
                })
    return rows, fingerprints


def mean(rows, key: str) -> float:
    values = [float(row[key]) for row in rows if row[key] is not None]
    return round(statistics.mean(values), 4)


class OfflineAnswererSwitchTests(unittest.TestCase):
    def test_default_config_fingerprint_is_v1_and_matches_report_f1(self):
        observed: dict[str, dict[str, float]] = {}
        with tempfile.TemporaryDirectory() as directory:
            cache = lab_cache.ArtifactCache(Path(directory) / "cache")
            for preset, path in (("B0", REFERENCE_B0), ("R0", REFERENCE_R0_REPORT)):
                config = lab_config.RunConfig.load(path)
                self.assertEqual(config.offline_answerer, lab_config.OFFLINE_ANSWERER_EXTRACTIVE)
                rows, fingerprints = measure_offline(config, cache)
                self.assertEqual(len(rows), 80)
                self.assertEqual(fingerprints, {fingerprint("offline-extractive-v1")})
                observed[preset] = {
                    "answer_f1": mean(rows, "answer_f1"),
                    "evidence_recall": mean(rows, "evidence_recall"),
                }
        self.assertEqual(observed["B0"], {"answer_f1": 0.0354, "evidence_recall": 0.5435})
        self.assertEqual(observed["R0"], {"answer_f1": 0.0054, "evidence_recall": 0.4018})

    def test_offline_qa_switch_changes_fingerprint_to_v2(self):
        data = lab_config.RunConfig.load(REFERENCE_B0).to_dict()
        data["use"] = {"offline_answerer": lab_config.OFFLINE_ANSWERER_OFFLINE_QA}
        config = lab_config.RunConfig.from_dict(data)
        self.assertEqual(config.offline_answerer, lab_config.OFFLINE_ANSWERER_OFFLINE_QA)
        with tempfile.TemporaryDirectory() as directory:
            cache = lab_cache.ArtifactCache(Path(directory) / "cache")
            ctx = executor.build_context(plan_for(config, "conv-26"), "conv-26",
                                         offline=True, cache=cache)
        self.assertEqual(ctx.llm.offline_answerer, lab_config.OFFLINE_ANSWERER_OFFLINE_QA)
        self.assertEqual(ctx.llm.fingerprint(), fingerprint("offline-extractive-v2"))
        self.assertNotEqual(ctx.llm.fingerprint(), fingerprint("offline-extractive-v1"))

    def test_unknown_offline_answerer_is_rejected(self):
        data = lab_config.RunConfig.load(REFERENCE_B0).to_dict()
        data["use"] = {"offline_answerer": "does_not_exist"}
        with self.assertRaises(lab_config.ConfigError) as caught:
            lab_config.RunConfig.from_dict(data)
        self.assertTrue(any(lab_config.OFFLINE_ANSWERER_PATH in problem
                            for problem in caught.exception.problems))

    def test_web_demo_preset_opts_into_offline_qa(self):
        out = webapp.post("/api/v2/runs", {
            "sample": "conv-26", "preset": "B0",
            "question": "What did Caroline do last Friday?", "offline": True,
        })
        try:
            self.assertEqual(out["model"]["offline_answerer"],
                             lab_config.OFFLINE_ANSWERER_OFFLINE_QA)
        finally:
            (ROOT / "runs" / "web" / f"{out['run_id']}.json").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
