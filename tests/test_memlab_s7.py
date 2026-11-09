"""S7a tests: coupling math on synthetic SQLite rows; no model needed."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from memlab.experiments import compiler, coupling, coupling_cli, spec as spec_module
from memlab.experiments.store import ResultStore

E2_SPEC = Path(__file__).resolve().parent.parent / "configs" / "experiments" / "e2-coupling.json"


def add_run(store, run_id, *, module="graph", llm="m1", metrics=()):
    store.upsert_run({
        "run_id": run_id, "spec_id": "E1", "design": "single_factor",
        "config_hash": "sha256:" + run_id, "effective_config": {},
        "environment": {"llm": {"model": llm}},
        "dataset": {}, "factors": {"module": module},
    }, status="complete")
    for qid, values in metrics:
        store.add_metrics(run_id, qid, values)


class CouplingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "runs.sqlite"
        self.store = ResultStore(self.db)
        # A: retrieval works on 2/3 but the answer is wrong; C is wrong on the
        # only fully retrieved one. B: retrieval and answer both work.
        add_run(self.store, "A", module="graph", llm="m1", metrics=[
            ("q0", {"evidence_recall": 1.0, "answer_f1": 0.0}),
            ("q1", {"evidence_recall": 1.0, "answer_f1": 0.0}),
            ("q2", {"evidence_recall": 0.0, "answer_f1": 1.0}),
        ])
        add_run(self.store, "B", module="rerank", llm="m2", metrics=[
            ("q0", {"evidence_recall": 1.0, "answer_f1": 1.0}),
            ("q1", {"evidence_recall": 1.0, "answer_f1": 1.0}),
        ])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_conversion_is_conditional_on_the_gate(self):
        row = coupling.conversion(self.store, "A", gate="evidence_recall", gate_min=1.0)
        self.assertEqual((row.n_total, row.n_gated, row.n_success), (3, 2, 0))
        self.assertEqual(row.conversion, 0.0)
        row_b = coupling.conversion(self.store, "B", gate="evidence_recall")
        self.assertEqual(row_b.conversion, 1.0)

    def test_conversion_table(self):
        rows = coupling.conversion_table(self.store)
        self.assertEqual({row["run_id"] for row in rows}, {"A", "B"})
        self.assertEqual([row["conversion"] for row in rows if row["run_id"] == "B"], [1.0])

    def test_oracle_gap(self):
        gap = coupling.oracle_gap(self.store, "A", "B", metric="answer_f1")
        self.assertEqual(gap["system"], 0.3333)
        self.assertEqual(gap["oracle"], 1.0)
        self.assertEqual(gap["gap"], 0.6667)

    def test_bottleneck_diagnosis(self):
        result = coupling.bottleneck(self.store, "A")
        self.assertEqual(result["diagnosis"], "use_or_merge_bottleneck")
        self.assertEqual(result["conversion"]["n_gated"], 2)

    def test_group_and_llm_attribution(self):
        groups = coupling.group_metric(self.store, "answer_f1", factor="module")
        self.assertEqual({row["group"] for row in groups}, {"graph", "rerank"})
        llm = coupling.llm_attribution(self.store, "answer_f1")
        self.assertEqual({row["llm"] for row in llm}, {"m1", "m2"})
        self.assertIsNotNone(coupling.eta_squared([[0.0, 0.0], [1.0, 1.0]]))

    def test_cli_outputs_json(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = coupling_cli.main(["--db", str(self.db), "--run", "A"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["conversion"]["conversion"], 0.0)


class SpecTests(unittest.TestCase):
    def test_e2_spec_is_analysis_only(self):
        spec = spec_module.load(E2_SPEC)
        self.assertEqual(spec.design, "coupling_analysis")
        with self.assertRaises(spec_module.SpecError):
            compiler.compile_spec(spec)


if __name__ == "__main__":
    unittest.main()
