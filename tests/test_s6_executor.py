"""S6 prerequisite tests: S5 Runner can execute the S4 module pipeline."""
import tempfile
import unittest
from pathlib import Path

from memlab import cache as lab_cache
from memlab import config as lab_config
from memlab import runtime
from memlab.experiments import compiler, executor, runner, store as store_module
from memwb import dataset, evaluation

REFERENCE_R0 = lab_config.ROOT / "configs" / "reference-r0.json"


def r0_plan(run_id="r-s6-test", config=None, planner="rule_router"):
    data = config or lab_config.RunConfig.load(REFERENCE_R0).to_dict()
    if planner:
        data["planner"] = {"impl": planner, "params": {}}
    digest = lab_config.digest(data)
    return compiler.RunPlan(
        run_id=run_id, spec_id="S6", design="smoke", config=data,
        requested_config=data, effective_config=data, config_hash=digest,
        environment=data.get("environment"), dataset={"samples": ["conv-26"]}, factors={},
    )


def questions(limit=2):
    sample = dataset.store().get("conv-26")
    return [runner.Question("conv-26", index, qa)
            for index, qa in evaluation.stratified(sample.get("qa", []), limit)]


class E2EExecutorTests(unittest.TestCase):
    def test_executor_runs_r0_without_runtime_and_returns_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            execute = executor.make_e2e_executor(offline=True, cache_root=Path(directory) / "cache")
            result = execute(r0_plan(), questions(1)[0])
        for key in ("answer", "retrieved_turns", "tokens", "latency_ms", "candidates"):
            self.assertIn(key, result)
        self.assertEqual(result["_meta"]["executor"], "e2e")
        self.assertTrue(result["_meta"]["offline"])
        self.assertEqual(result["_meta"]["store_units"], 628)  # R0 meta+mem0 on conv-26

    def test_r0_runtime_still_refused_but_executor_is_explicit(self):
        with self.assertRaises(Exception):
            runtime.Runtime.load(REFERENCE_R0)
        with tempfile.TemporaryDirectory() as directory:
            execute = executor.make_e2e_executor(offline=True, cache_root=Path(directory) / "cache")
            self.assertIn("answer", execute(r0_plan(), questions(1)[0]))

    def test_runner_writes_answer_recall_tokens_seconds_and_ndcg(self):
        with tempfile.TemporaryDirectory() as directory:
            execute = executor.make_e2e_executor(offline=True, cache_root=Path(directory) / "cache")
            plans = [r0_plan("r-s6-a", planner="none"), r0_plan("r-s6-b", planner="rule_router")]
            db = Path(directory) / "s6.sqlite"
            with store_module.ResultStore(db) as store:
                machine = runner.Runner(store, executor=execute)
                results = machine.run(None, plans, questions=questions(2))
                metrics = {row["metric"] for row in store.metrics()}
                runs = store.runs()
        self.assertEqual(results[0]["errors"], 0)
        self.assertEqual(results[1]["errors"], 0)
        self.assertTrue({"answer_f1", "evidence_recall", "tokens", "seconds", "ndcg"} <= metrics)
        self.assertEqual(len(runs), 2)
        self.assertEqual({row["status"] for row in runs}, {"complete"})

    def test_k_executor_reports_health_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            execute = executor.make_k_executor(policy="consolidate", params={"threshold": 0.9},
                                               offline=True,
                                               cache=lab_cache.ArtifactCache(Path(directory) / "cache"))
            result = execute(r0_plan(), questions(1)[0])
        self.assertIn("staleness", result)
        self.assertIn("contradiction_rate", result)
        self.assertIn("update_correctness", result)
        self.assertEqual(result["_meta"]["executor"], "k")


if __name__ == "__main__":
    unittest.main()
