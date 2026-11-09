"""Repair-session tests: runnable gate, per-plan datasets, resume, dedupe.

These tests protect the *experiment* contract, not just the code: a plan that
cannot build or that varies an unconsumed axis must not look like a valid point in
a screening matrix.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from memlab import config as lab_config
from memlab.experiments import cli, compiler, runner, spec as spec_module, store as store_module

ROOT = lab_config.ROOT
REFERENCE_B0 = ROOT / "configs" / "reference-b0.json"
SPEC_DIR = ROOT / "configs" / "experiments"
E1_ADOPTION = SPEC_DIR / "e1-adoption.json"
E1_SCREENING = SPEC_DIR / "e1-screening.json"
E3_FACTORIAL = SPEC_DIR / "e3-factorial.json"
E4_GRID = SPEC_DIR / "e4-environment-grid.json"


def plans_for(path: Path):
    return compiler.compile_spec(spec_module.load(path))


def write_spec(directory: Path, payload: dict, name="spec.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def minimal_spec(**overrides):
    payload = {
        "id": "T-REPAIR",
        "design": "single_factor",
        "reference_config": str(REFERENCE_B0),
        "environment": {"seed": 13},
        "dataset": {"adapter": "locomo", "samples": ["conv-26"], "question_limit": 2},
        "factors": [{"id": "planner.impl", "levels": ["none", "rule_router"]}],
    }
    payload.update(overrides)
    return payload


def scale_spec(directory: Path) -> Path:
    """Two data scales with different samples/question limits (E4 shape)."""
    payload = minimal_spec(
        id="T-SCALES", design="environment_grid", factors=[],
        grid={
            "llm": [{"id": "L1", "model": "m1"}],
            "data_scale": [
                {"id": "S1", "samples": ["conv-26"], "question_limit": 2},
                {"id": "S2", "samples": ["conv-26"], "question_limit": 3},
            ],
            "scene": [{"id": "PA"}],
        },
        candidates=[{"id": "R0", "config": "R0_reference"}],
    )
    return write_spec(directory, payload)


class RunnableGateTests(unittest.TestCase):
    def test_e1_screening_blocks_the_audited_seven(self):
        blocked = [plan for plan in plans_for(E1_SCREENING) if not plan.runnable]
        schema = [plan for plan in blocked
                  if plan.factors.get("schema.impl") in {"hmem", "structmem", "amem"}]
        cot = [plan for plan in blocked if "schema.params.cot" in plan.factors]
        graph = [plan for plan in blocked
                 if plan.factors.get("graph.repr.impl") in {"event_sparse", "community"}]
        self.assertEqual((len(schema), len(cot), len(graph)), (3, 2, 2))
        for plan in schema:
            self.assertIn("unknown schema", plan.runnable_reasons[0])
        for plan in cot:
            self.assertIn("cot", plan.runnable_reasons[0])
            self.assertIn("does not accept", plan.runnable_reasons[0])
        for plan in graph:
            self.assertIn("unknown graph.repr", plan.runnable_reasons[0])

    def test_additional_build_failures_are_also_gated(self):
        """The light build is stricter than the audit: it also catches post stages."""
        blocked = [plan for plan in plans_for(E1_SCREENING) if not plan.runnable]
        reasons = {tuple(sorted(plan.factors.items())): plan.runnable_reasons[0] for plan in blocked}
        self.assertEqual(sum(1 for plan in blocked
                             if plan.factors.get("post.mmr.impl") == "none"), 1)
        self.assertEqual(sum(1 for plan in blocked
                             if plan.factors.get("post.decay.impl") == "none"), 1)
        self.assertEqual(sum(1 for plan in blocked
                             if plan.factors.get("post.compress.impl") == "llm_summary"), 1)
        self.assertIn("lambda", reasons[(("post.mmr.impl", "none"),)])
        self.assertIn("lambda", reasons[(("post.decay.impl", "none"),)])
        self.assertIn("unknown post.compress", reasons[(("post.compress.impl", "llm_summary"),)])
        # 7 audited + 3 discovered by the real construction path.
        self.assertEqual(len(blocked), 10)

    def test_e1a_e3_e4_are_buildable(self):
        self.assertEqual(len(plans_for(E1_ADOPTION)), 22)
        self.assertEqual(len(plans_for(E3_FACTORIAL)), 16)
        self.assertEqual(len(plans_for(E4_GRID)), 27)
        for path in (E1_ADOPTION, E3_FACTORIAL, E4_GRID):
            for plan in plans_for(path):
                with self.subTest(spec=path.name, run=plan.run_id):
                    self.assertTrue(plan.runnable, plan.runnable_reasons)

    def test_no_op_axes_are_never_valid_factors(self):
        self.assertEqual(set(compiler.NO_OP_AXES),
                         {"graph.retrieval.impl", "post.dedupe", "write.consolidator"})
        plans = plans_for(E1_SCREENING)
        no_op = [plan for plan in plans if "graph.retrieval.impl" in plan.factors]
        # dual_channel equals the R0 default and is folded into the base config;
        # the other three levels remain as explicit inert plans.
        self.assertEqual(len(no_op), 3)
        for plan in no_op:
            self.assertFalse(plan.valid)
            self.assertEqual(plan.no_op_factors, ("graph.retrieval.impl",))
        self.assertFalse(any(plan.valid and plan.no_op_factors for plan in plans))

    def test_planner_fallback_is_a_warning_not_silent(self):
        plans = plans_for(E1_SCREENING)
        reaper = [plan for plan in plans if plan.factors.get("planner.impl") == "reaper"]
        self.assertTrue(reaper)
        for plan in reaper:
            self.assertTrue(plan.runnable)
            self.assertTrue(any("falls back to rule_router" in warning for warning in plan.warnings))

    def test_cli_sweep_excludes_invalid_plans_by_default(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.main(["sweep", "--spec", str(E1_SCREENING), "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["runs"], 74)
        self.assertEqual(payload["valid_runs"], 61)
        self.assertEqual(payload["selected_runs"], 61)
        self.assertEqual(payload["excluded_unrunnable"], 10)
        self.assertEqual(payload["excluded_no_op"], 3)
        self.assertEqual(payload["duplicates"], 28)


class DedupeTests(unittest.TestCase):
    def test_every_compiled_matrix_has_unique_config_hashes(self):
        for path in (E1_ADOPTION, E1_SCREENING, E3_FACTORIAL, E4_GRID):
            plans = plans_for(path)
            with self.subTest(spec=path.name):
                self.assertEqual(len({plan.config_hash for plan in plans}), len(plans))
                self.assertEqual(len({plan.run_id for plan in plans}), len(plans))

    def test_aliases_record_dropped_duplicates(self):
        adoption = plans_for(E1_ADOPTION)
        self.assertEqual(sum(len(plan.aliases) for plan in adoption), 1)
        grid = plans_for(E4_GRID)
        self.assertEqual(len(grid), 27)
        self.assertEqual(sum(len(plan.aliases) for plan in grid), 108)
        for plan in grid:
            self.assertEqual(len(plan.aliases), 4)
            # The keeper must be the candidate whose label matches the R0 config;
            # B0/CHEAP/QUALITY/E3_WINNER are aliases, not independent candidates.
            self.assertEqual(plan.factors["candidate"], "R0")
        self.assertTrue(any("is not defined" in note for plan in grid for note in plan.notes))
        self.assertTrue(any("candidate" in alias for alias in grid[0].aliases))

    def test_duplicate_alias_on_noop_axis_is_annotated(self):
        plans = plans_for(E1_SCREENING)
        annotated = [plan for plan in plans
                     if any("duplicate alias varies no-op axis" in note for note in plan.notes)]
        self.assertTrue(annotated)


class PlanDatasetTests(unittest.TestCase):
    def test_runner_uses_each_plans_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = spec_module.load(scale_spec(Path(directory)))
            plans = compiler.compile_spec(spec)
            self.assertEqual(len(plans), 2)
            seen = {}

            def executor(plan, question):
                seen.setdefault(plan.run_id, []).append(question.qid)
                return {"answer": question.qa["answer"]}

            with store_module.ResultStore(Path(directory) / "runs.sqlite") as store:
                runner.Runner(store, executor=executor, resume=False).run(spec, plans)
        limits = {plan.dataset["question_limit"]: len(seen[plan.run_id]) for plan in plans}
        self.assertEqual(limits, {2: 2, 3: 3})

    def test_explicit_questions_override_every_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = spec_module.load(scale_spec(Path(directory)))
            plans = compiler.compile_spec(spec)
            questions = runner.load_questions(spec, limit=1, samples=["conv-26"])
            self.assertEqual(len(questions), 1)
            with store_module.ResultStore(Path(directory) / "runs.sqlite") as store:
                machine = runner.Runner(store, executor=lambda plan, q: {"answer": q.qa["answer"]})
                results = machine.run(spec, plans, questions=questions)
        self.assertEqual([row["attempted"] for row in results], [1, 1])


class ResumeErrorTests(unittest.TestCase):
    def test_error_metric_is_not_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = plans_for(E1_ADOPTION)[0]
            with store_module.ResultStore(Path(directory) / "runs.sqlite") as store:
                store.upsert_run(plan, status="running")
                store.add_metric(plan.run_id, "conv-26:0", "error", 1.0)
                self.assertFalse(store.completed(plan.run_id, "conv-26:0"))
                self.assertTrue(store.errored(plan.run_id, "conv-26:0"))
                store.add_metric(plan.run_id, "conv-26:0", "answer_f1", 0.5)
                self.assertTrue(store.completed(plan.run_id, "conv-26:0"))
                self.assertTrue(store.errored(plan.run_id, "conv-26:0"))

    def test_resume_skips_then_retries_errors(self):
        def failing(plan, question):
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as directory:
            spec = spec_module.load(write_spec(Path(directory), minimal_spec()))
            plan = compiler.compile_spec(spec)[0]
            db = Path(directory) / "runs.sqlite"
            with store_module.ResultStore(db) as store:
                first = runner.Runner(store, executor=failing, resume=False)
                result = first.run_plan(plan, runner.load_questions(spec, limit=2))
                self.assertEqual((result["attempted"], result["errors"]), (2, 2))
                self.assertEqual(store.get_run(plan.run_id)["status"], "complete_with_errors")

                resumed = runner.Runner(store, executor=failing).run_plan(
                    plan, runner.load_questions(spec, limit=2))
                self.assertEqual((resumed["attempted"], resumed["skipped_errors"]), (0, 2))
                self.assertEqual(store.get_run(plan.run_id)["status"], "complete_with_errors")

                retried = runner.Runner(store, executor=failing, retry_errors=True).run_plan(
                    plan, runner.load_questions(spec, limit=2))
                self.assertEqual((retried["attempted"], retried["errors"]), (2, 2))


if __name__ == "__main__":
    unittest.main()
