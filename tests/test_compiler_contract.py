"""Compiler output must be a valid RunConfig, not just a JSON matrix."""
import unittest
from pathlib import Path

from memlab import config
from memlab.experiments import compiler, spec as spec_module

ROOT = Path(__file__).resolve().parent.parent
SPECS = [
    ROOT / "configs/experiments/e1-adoption.json",
    ROOT / "configs/experiments/e1-screening.json",
    ROOT / "configs/experiments/e3-factorial.json",
    ROOT / "configs/experiments/e4-environment-grid.json",
]


class CompilerContractTests(unittest.TestCase):
    def test_every_compiled_plan_is_a_valid_run_config(self):
        for path in SPECS:
            with self.subTest(spec=path.name):
                plans = compiler.compile_spec(spec_module.load(path))
                self.assertTrue(plans)
                for plan in plans:
                    config.RunConfig.from_dict(plan.effective_config)

    def test_short_llm_environment_is_normalized(self):
        plans = compiler.compile_spec(spec_module.load(SPECS[0]))
        self.assertIsInstance(plans[0].effective_config["environment"]["llm"], dict)
        self.assertEqual(plans[0].effective_config["environment"]["llm"]["model"], "qwen3.8:27b-q4_K_M")

    def test_graph_absent_downgrades_invalidate_edge(self):
        plans = compiler.compile_spec(spec_module.load(SPECS[1]))
        bad = [p for p in plans if p.effective_config.get("graph", {}).get("repr", {}).get("impl") == "none"]
        self.assertTrue(bad)
        for plan in bad:
            self.assertEqual(plan.effective_config["temporal"]["params"]["conflict_policy"], "keep_both")
            self.assertTrue(any("capability closure" in note for note in plan.notes))


if __name__ == "__main__":
    unittest.main()
