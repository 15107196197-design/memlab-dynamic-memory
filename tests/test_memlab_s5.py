"""S5 tests: spec loading, compilation, SQLite store, runner resume/sharding, CLI."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from memlab import config as lab_config
from memlab.experiments import analysis, cli, compiler, runner, spec as spec_module, store as store_module

ROOT = lab_config.ROOT
REFERENCE_B0 = ROOT / "configs" / "reference-b0.json"
E1_ADOPTION = ROOT / "configs" / "experiments" / "e1-adoption.json"
E3_FACTORIAL = ROOT / "configs" / "experiments" / "e3-factorial.json"


def write_spec(directory: Path, payload: dict, name="spec.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def minimal_spec(**overrides):
    payload = {
        "id": "T1",
        "design": "single_factor",
        "reference_config": str(REFERENCE_B0),
        "environment": {"seed": 13},
        "dataset": {"adapter": "locomo", "samples": ["conv-26"], "question_limit": 2},
        "factors": [{"id": "planner.impl", "levels": ["none", "rule_router"]}],
    }
    payload.update(overrides)
    return payload


class SpecTests(unittest.TestCase):
    def test_load_e1_adoption(self):
        spec = spec_module.load(E1_ADOPTION)
        self.assertEqual(spec.id, "E1.1-module-adoption")
        self.assertEqual(spec.design, "single_factor_adoption")
        self.assertTrue(spec.reference_off.is_file())
        self.assertTrue(spec.reference_on.is_file())

    def test_reject_missing_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_spec(Path(directory), minimal_spec(reference_config="nope.json"))
            with self.assertRaises(spec_module.SpecError):
                spec_module.load(path)

    def test_reject_unknown_design(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_spec(Path(directory), minimal_spec(design="magic"))
            with self.assertRaises(spec_module.SpecError):
                spec_module.load(path)


class CompilerTests(unittest.TestCase):
    def test_single_factor_expands_levels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_spec(Path(directory), minimal_spec())
            plans = compiler.compile_spec(spec_module.load(path))
        self.assertEqual(len(plans), 2)
        values = [plan.effective_config["planner"]["impl"] for plan in plans]
        self.assertEqual(values, ["none", "rule_router"])
        self.assertTrue(all(plan.config_hash.startswith("sha256:") for plan in plans))

    def test_derived_rules_close_graph_dependency(self):
        spec = spec_module.load(E1_ADOPTION)
        plans = compiler.compile_spec(spec)
        self.assertEqual(len(plans), 23)
        graph_on = [p for p in plans if p.factors.get("module") == "graph" and p.factors.get("baseline") == "add_from_B0"][0]
        self.assertEqual(graph_on.effective_config["graph"]["repr"]["impl"], "entity_triple")
        self.assertEqual(graph_on.effective_config["graph"]["retrieval"]["impl"], "entity_subgraph")
        graph_off = [p for p in plans if p.factors.get("module") == "graph" and p.factors.get("baseline") == "remove_from_R0"][0]
        self.assertEqual(graph_off.effective_config["graph"]["retrieval"]["impl"], "slot_expand")
        temporal = [p for p in plans if p.factors.get("module") == "temporal"]
        self.assertEqual({p.factors["baseline"] for p in temporal}, {"remove_from_R0"})
        self.assertTrue(any("State-slot" in note for note in graph_off.notes))

    def test_fractional_half_fraction_has_16_runs(self):
        plans = compiler.compile_spec(spec_module.load(E3_FACTORIAL))
        self.assertEqual(len(plans), 16)
        signatures = {tuple(sorted(plan.factors.items())) for plan in plans}
        self.assertEqual(len(signatures), 16)

    def test_environment_grid_cross_product(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = minimal_spec(
                id="T2", design="environment_grid",
                grid={"llm": [{"id": "L1", "model": "m1"}, {"id": "L2", "model": "m2"}],
                      "data_scale": [{"id": "S1", "samples": ["conv-26"], "question_limit": 2}],
                      "scene": [{"id": "PA"}]},
                candidates=[{"id": "B0", "config": "B0"}],
                factors=[],
            )
            path = write_spec(Path(directory), payload)
            plans = compiler.compile_spec(spec_module.load(path))
        self.assertEqual(len(plans), 2)
        self.assertEqual({p.effective_config["environment"]["llm"]["model"] for p in plans}, {"m1", "m2"})


class StoreTests(unittest.TestCase):
    def test_metric_roundtrip_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "r.sqlite"
            with store_module.ResultStore(db) as store:
                plan = compiler.compile_spec(spec_module.load(E1_ADOPTION))[0]
                store.upsert_run(plan, status="running")
                store.add_metric(plan.run_id, "conv-26:0", "answer_f1", 0.5)
                store.add_metric(plan.run_id, "conv-26:1", "answer_f1", 1.0)
                self.assertTrue(store.completed(plan.run_id, "conv-26:0"))
                self.assertFalse(store.completed(plan.run_id, "conv-26:2"))
                rows = store.summary("answer_f1")
                self.assertEqual(rows[0]["n"], 2)
                self.assertAlmostEqual(rows[0]["mean"], 0.75)
                store.set_status(plan.run_id, "complete")
                self.assertEqual(store.get_run(plan.run_id)["status"], "complete")


class RunnerTests(unittest.TestCase):
    def test_fake_executor_and_resume(self):
        calls = []

        def executor(plan, question):
            calls.append(question.qid)
            return {"answer": question.qa["answer"], "retrieved_turns": question.qa.get("evidence", [])}

        with tempfile.TemporaryDirectory() as directory:
            spec = spec_module.load(write_spec(Path(directory), minimal_spec()))
            plans = compiler.compile_spec(spec)
            questions = runner.load_questions(spec, limit=2)
            self.assertEqual(len(questions), 2)
            db = Path(directory) / "runs.sqlite"
            with store_module.ResultStore(db) as store:
                machine = runner.Runner(store, executor=executor)
                first = machine.run(spec, plans[:1], questions=questions)
                self.assertEqual(first[0]["attempted"], 2)
                self.assertEqual(len(calls), 2)
                second = machine.run(spec, plans[:1], questions=questions)
                self.assertEqual(second[0]["attempted"], 0)
                self.assertEqual(second[0]["skipped"], 2)
                self.assertEqual(len(calls), 2)
                rows = analysis.run_table(store, "answer_f1")
                self.assertEqual(rows[0]["answer_f1"], 1.0)

    def test_three_configs_ten_questions_write_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = minimal_spec(
                factors=[{"id": "fusion.impl", "levels": ["single_channel", "rrf", "weighted_rrf"]}],
                dataset={"adapter": "locomo", "samples": ["conv-26"], "question_limit": 10},
            )
            spec = spec_module.load(write_spec(Path(directory), payload))
            plans = compiler.compile_spec(spec)
            questions = runner.load_questions(spec, limit=10)
            self.assertEqual((len(plans), len(questions)), (3, 10))
            db = Path(directory) / "runs.sqlite"
            with store_module.ResultStore(db) as store:
                machine = runner.Runner(store, executor=lambda plan, q: {"answer": q.qa["answer"]})
                machine.run(spec, plans, questions=questions)
                self.assertEqual(len(store.runs()), 3)
                self.assertEqual(len(store.metrics(metric="answer_f1")), 30)
                self.assertEqual({row["status"] for row in store.runs()}, {"complete"})

    def test_sharding_selects_one_question(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = spec_module.load(write_spec(Path(directory), minimal_spec()))
            questions = runner.load_questions(spec, limit=2)
            db = Path(directory) / "runs.sqlite"
            with store_module.ResultStore(db) as store:
                machine = runner.Runner(store, executor=lambda plan, q: {"answer": q.qa["answer"]},
                                        shard=1, shards=2)
                result = machine.run_plan(compiler.compile_spec(spec)[0], questions)
                self.assertEqual(result["attempted"], 1)


class CliTests(unittest.TestCase):
    def test_sweep_dry_run_outputs_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_spec(Path(directory), minimal_spec())
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["sweep", "--spec", str(path), "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["runs"], 2)
        self.assertTrue(payload["dry_run"])


if __name__ == "__main__":
    unittest.main()
