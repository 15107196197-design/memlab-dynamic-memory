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
    def test_e1_screening_has_no_unrunnable_plans_left(self):
        plans = plans_for(E1_SCREENING)
        blocked = [plan for plan in plans if not plan.runnable]
        self.assertEqual(blocked, [])
        # The 10 blocked plans from the audit session were closed by one of two
        # legitimate moves: implement (event_sparse, post.mmr/decay=none) or remove
        # from the executable factors with a recorded deferral (the rest).
        event_sparse = [plan for plan in plans
                        if plan.factors.get("graph.repr.impl") == "event_sparse"]
        self.assertEqual(len(event_sparse), 1)
        self.assertTrue(event_sparse[0].valid)

    def test_deferred_levels_are_recorded_and_absent_from_factors(self):
        spec = spec_module.load(E1_SCREENING)
        deferred = spec.deferred
        self.assertTrue(deferred)
        factors = {factor["id"]: factor for factor in spec.factors}
        for item in deferred:
            self.assertTrue(item["reason"], item)
            self.assertTrue(item["status"], item)
            self.assertTrue(item["planned_in"], item)
            factor = factors.get(item["id"])
            if factor is not None:
                overlap = set(item["levels"]) & set(factor.get("levels") or [])
                self.assertEqual(overlap, set(), f"{item['id']} still has deferred levels")
        plans = plans_for(E1_SCREENING)
        for item in deferred:
            for plan in plans:
                if item["id"] in plan.factors:
                    self.assertNotIn(plan.factors[item["id"]], item["levels"])
        statuses = {item["status"] for item in deferred}
        self.assertIn("deferred_blocked_on_llm_extraction", statuses)
        self.assertIn("deferred_blocked_on_ollama", statuses)

    def test_deferred_entry_without_reason_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = minimal_spec(deferred=[{"id": "schema.impl", "levels": ["hmem"],
                                              "status": "deferred"}])
            path = write_spec(Path(directory), payload)
            with self.assertRaises(spec_module.SpecError) as caught:
                spec_module.load(path)
            self.assertTrue(any("reason" in problem for problem in caught.exception.problems))

    def test_disabled_stage_params_are_not_injected(self):
        """post.mmr=none / post.decay=none used to get a lambda they reject."""
        plans = plans_for(E1_SCREENING)
        for factor, path in (("post.mmr.impl", "post.mmr.params.lambda"),
                             ("post.decay.impl", "post.decay.params.lambda")):
            plan = next(plan for plan in plans if plan.factors.get(factor) == "none")
            with self.subTest(factor=factor):
                self.assertTrue(plan.runnable, plan.runnable_reasons)
                self.assertTrue(plan.valid)
                self.assertIsNone(compiler.get_path(plan.effective_config, path))
                self.assertFalse(any("lambda" in note for note in plan.notes))

    def test_event_sparse_does_not_keep_three_layer_params(self):
        plan = next(plan for plan in plans_for(E1_SCREENING)
                    if plan.factors.get("graph.repr.impl") == "event_sparse")
        self.assertEqual(plan.effective_config["graph"]["repr"], {"impl": "event_sparse", "params": {}})

    def test_e1a_e3_e4_are_buildable(self):
        self.assertEqual(len(plans_for(E1_ADOPTION)), 22)
        self.assertEqual(len(plans_for(E3_FACTORIAL)), 16)
        self.assertEqual(len(plans_for(E4_GRID)), 108)
        for path in (E1_ADOPTION, E3_FACTORIAL, E4_GRID):
            for plan in plans_for(path):
                with self.subTest(spec=path.name, run=plan.run_id):
                    self.assertTrue(plan.runnable, plan.runnable_reasons)

    def test_no_op_axes_are_never_valid_factors(self):
        # R3 wired graph.retrieval.impl into the graph channel, so it must leave
        # the inert-axis list; the remaining two axes are still unconsumed.
        self.assertEqual(set(compiler.NO_OP_AXES), {"post.dedupe", "write.consolidator"})
        plans = plans_for(E1_SCREENING)
        graph_impl = [plan for plan in plans if "graph.retrieval.impl" in plan.factors]
        # dual_channel equals the R0 default and is folded into the base config;
        # the other three levels now execute through the graph-retrieval dispatch.
        self.assertEqual(len(graph_impl), 3)
        for plan in graph_impl:
            self.assertTrue(plan.valid, plan.runnable_reasons)
            self.assertEqual(plan.no_op_factors, ())
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
        self.assertEqual(payload["runs"], 67)
        self.assertEqual(payload["valid_runs"], 67)
        self.assertEqual(payload["selected_runs"], 67)
        self.assertEqual(payload["excluded_unrunnable"], 0)
        self.assertEqual(payload["excluded_no_op"], 0)
        self.assertEqual(payload["duplicates"], 28)
        self.assertEqual(payload["deferred_factors"], 5)
        self.assertTrue(all(item["reason"] for item in payload["deferred"]))


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
        # E4 candidates now resolve to real reference files, so none is an alias.
        grid = plans_for(E4_GRID)
        self.assertEqual(len(grid), 108)
        self.assertEqual(sum(len(plan.aliases) for plan in grid), 0)
        self.assertEqual({plan.factors["candidate"] for plan in grid},
                         {"B0", "R0", "CHEAP", "QUALITY"})
        self.assertFalse(any("is not defined" in note for plan in grid for note in plan.notes))
        self.assertFalse(any(note.startswith("warning:") for plan in grid for note in plan.notes))

    def test_e4_candidates_use_distinct_reference_configs(self):
        grid = plans_for(E4_GRID)
        self.assertEqual({plan.config["preset"] for plan in grid},
                         {"B0", "R0", "CHEAP", "QUALITY"})
        self.assertEqual(len({plan.config_hash for plan in grid}), 108)
        cheap = next(plan for plan in grid if plan.factors["candidate"] == "CHEAP")
        quality = next(plan for plan in grid if plan.factors["candidate"] == "QUALITY")
        r0 = next(plan for plan in grid if plan.factors["candidate"] == "R0")
        self.assertEqual(cheap.config["schema"]["params"]["fields"], 6)
        self.assertEqual(quality.config["schema"]["params"]["fields"], 10)
        self.assertNotEqual(cheap.config_hash, r0.config_hash)
        self.assertNotEqual(quality.config_hash, r0.config_hash)
        self.assertEqual({plan.config["schema"]["impl"] for plan in grid
                          if plan.factors["candidate"] == "B0"}, {"legacy_flat"})

    def test_e3_winner_is_deferred_not_silently_dropped(self):
        spec = spec_module.load(E4_GRID)
        entry = next(item for item in spec.deferred if item["id"] == "candidate")
        self.assertIn("E3_WINNER", entry["levels"])
        self.assertEqual(entry["status"], "deferred_blocked_on_E3")
        self.assertNotIn("E3_WINNER", {plan.factors["candidate"] for plan in plans_for(E4_GRID)})

    def test_duplicate_alias_on_noop_axis_is_annotated(self):
        config = {"seed": 13}
        digest = lab_config.digest(config)
        base = compiler.RunPlan(
            run_id="a", spec_id="T", design="full_factorial", config=config,
            requested_config=config, effective_config=config, config_hash=digest,
            environment={}, dataset={}, factors={"f": 1},
            no_op_factors=("post.dedupe",),
        )
        duplicate = compiler.RunPlan(
            run_id="b", spec_id="T", design="full_factorial", config=config,
            requested_config=config, effective_config=config, config_hash=digest,
            environment={}, dataset={}, factors={"f": 2},
        )
        kept = compiler.dedupe_plans([base, duplicate])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].run_id, "b")
        self.assertTrue(any("duplicate alias varies no-op axis" in note for note in kept[0].notes))


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
