"""Judge and Runner-judge integration tests; no model or network."""
import tempfile
import unittest
from pathlib import Path

from memlab import config as lab_config
from memlab.experiments import compiler, runner
from memlab.experiments.store import ResultStore
from memlab.judge import Judge


class FakeLLM:
    effective_model = "fake-judge"

    def __init__(self, payload=None, error=None):
        self.payload = payload or {"correct": True, "faithful": True, "confidence": 0.9, "reason": "ok"}
        self.error = error
        self.prompts = []

    def generate(self, prompt, json_mode=False, max_tokens=None):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.payload


def plan(run_id="r-judge"):
    data = lab_config.RunConfig.load(lab_config.ROOT / "configs" / "reference-b0.json").to_dict()
    digest = lab_config.digest(data)
    return compiler.RunPlan(
        run_id=run_id, spec_id="J", design="smoke", config=data,
        requested_config=data, effective_config=data, config_hash=digest,
        environment=data.get("environment"), dataset={}, factors={},
    )


def question():
    return runner.Question("conv-26", 0, {"question": "q", "answer": "a", "category": 1})


class JudgeTests(unittest.TestCase):
    def test_score_returns_numeric_metrics(self):
        judge = Judge(FakeLLM())
        result = judge.score("q", "a", "a", "evidence")
        self.assertEqual(result["judge_correct"], 1)
        self.assertEqual(result["judge_faithful"], 1)
        self.assertEqual(result["judge_model"], "fake-judge")

    def test_runner_writes_judge_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            with ResultStore(Path(directory) / "r.sqlite") as store:
                machine = runner.Runner(store, executor=lambda p, q: {"answer": "a"},
                                        judge=lambda p, q, result: {"judge_correct": 1, "judge_reason": "ok"})
                machine.run_plan(plan(), [question()])
                metrics = {row["metric"]: row["value"] for row in store.metrics()}
        self.assertEqual(metrics["judge_correct"], 1.0)

    def test_judge_failure_is_not_answer_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with ResultStore(Path(directory) / "r.sqlite") as store:
                def bad_judge(p, q, result):
                    raise RuntimeError("judge down")
                machine = runner.Runner(store, executor=lambda p, q: {"answer": "a"}, judge=bad_judge)
                machine.run_plan(plan(), [question()])
                metrics = {row["metric"]: row["value"] for row in store.metrics()}
                status = store.get_run("r-judge")["status"]
        self.assertEqual(metrics["judge_error"], 1.0)
        self.assertEqual(status, "complete")


if __name__ == "__main__":
    unittest.main()
