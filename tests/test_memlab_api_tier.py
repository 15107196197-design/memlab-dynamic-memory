"""API-tier experiment specs: provider metadata propagates, no local-scale claim."""
import unittest
from pathlib import Path

from memlab import config
from memlab.experiments import compiler, spec as spec_module

ROOT = Path(__file__).resolve().parent.parent
SPECS = [
    ROOT / "configs/experiments/e1-api-tier-grid.json",
    ROOT / "configs/experiments/e4-api-tier-grid.json",
]


class ApiTierTests(unittest.TestCase):
    def test_specs_compile_and_expose_tiers(self):
        for path in SPECS:
            with self.subTest(spec=path.name):
                spec = spec_module.load(path)
                plans = compiler.compile_spec(spec)
                self.assertTrue(plans)
                for plan in plans:
                    llm = plan.effective_config["environment"]["llm"]
                    self.assertEqual(llm["provider"], "openai_compatible")
                    self.assertTrue(llm["model"])
                    self.assertTrue(llm["base_url"])
                    self.assertTrue(llm["api_key_env"])
                    self.assertIn("api_tier", plan.factors)
                    self.assertTrue(any("not a local parameter-count scale" in note for note in plan.notes))
                    config.RunConfig.from_dict(plan.effective_config)

    def test_tiers_have_distinct_config_hashes(self):
        spec = spec_module.load(SPECS[0])
        plans = compiler.compile_spec(spec)
        tiers = {plan.factors["api_tier"] for plan in plans}
        self.assertEqual(len(tiers), 3)
        hashes = {plan.config_hash for plan in plans}
        self.assertEqual(len(hashes), len(plans))

    def test_local_llm_scale_is_deferred(self):
        spec = spec_module.load(SPECS[0])
        deferred = {item["id"]: item for item in spec.deferred}
        self.assertEqual(deferred["local_llm_scale"]["status"], "blocked_on_local_gpu")
        self.assertIn("module_llm_scale", deferred)


if __name__ == "__main__":
    unittest.main()
