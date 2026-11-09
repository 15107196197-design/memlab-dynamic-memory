"""Run a compiled matrix with resume, sharding and per-question metrics."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from memwb import dataset as legacy_dataset, evaluation

from .. import runtime as lab_runtime
from .compiler import RunPlan
from .spec import Spec
from .store import ResultStore


@dataclass(frozen=True)
class Question:
    sample_id: str
    index: int
    qa: dict[str, Any]

    @property
    def qid(self) -> str:
        return f"{self.sample_id}:{self.index}"


def load_questions(spec: Spec, *, limit: int | None = None, samples: Sequence[str] | None = None,
                   dataset: Mapping[str, Any] | None = None) -> list[Question]:
    """Load questions for one plan's dataset.

    ``limit``/``samples`` are explicit caller overrides; otherwise the dataset
    block (plan-level first, spec-level fallback) decides the conversations and
    question count.  E4 plans differ in both, so the runner must not load one
    global question set.
    """
    data = dict(dataset) if dataset is not None else spec.dataset
    store = legacy_dataset.store()
    ids = list(samples if samples is not None else data.get("samples") or store.ids())
    per_conversation = limit if limit is not None else data.get("question_limit")
    out: list[Question] = []
    for sample_id in ids:
        sample = store.get(sample_id)
        selected = evaluation.stratified(sample.get("qa", []), int(per_conversation) if per_conversation else 0)
        for index, qa in selected:
            out.append(Question(sample_id, index, qa))
    return out


def evaluate_result(result: Mapping[str, Any], question: Question) -> dict[str, Any]:
    values: dict[str, Any] = {}
    answer = result.get("answer")
    gold = question.qa.get("answer")
    if answer is not None and gold is not None:
        values["answer_f1"] = evaluation.answer_f1(str(answer), gold, question.qa.get("category"))
    retrieved = result.get("retrieved_turns")
    if isinstance(retrieved, list):
        recall = evaluation.recall(evaluation.evidence_turns(question.qa), retrieved)
        if recall is not None:
            values["evidence_recall"] = recall
    for key, value in result.items():
        if key.startswith("_") or isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values[key] = value
    return values


class Runner:
    """Execute plans; the executor is injectable so tests need no model."""

    def __init__(self, store: ResultStore, *, executor: Callable[[RunPlan, Question], Mapping[str, Any]] | None = None,
                 limit: int | None = None, shard: int = 0, shards: int = 1, resume: bool = True,
                 retry_errors: bool = False, log: Callable[[dict[str, Any]], None] | None = None):
        if shards <= 0 or not 0 <= shard < shards:
            raise ValueError("shard must satisfy 0 <= shard < shards")
        self.store = store
        self.executor = executor or default_executor
        self.limit = limit
        self.shard = shard
        self.shards = shards
        self.resume = resume
        self.retry_errors = retry_errors
        self.log = log

    def _selected(self, questions: Sequence[Question]) -> list[Question]:
        return [question for position, question in enumerate(questions) if position % self.shards == self.shard]

    def run_plan(self, plan: RunPlan, questions: Sequence[Question]) -> dict[str, Any]:
        self.store.upsert_run(plan, status="running")
        attempted = completed = skipped_errors = errors = 0
        for question in self._selected(questions):
            if self.resume:
                if self.store.completed(plan.run_id, question.qid):
                    completed += 1
                    continue
                # An error row is not "completed".  By default resume skips it to
                # avoid an infinite retry loop, but reports it separately; with
                # retry_errors the question is attempted again.
                if self.store.errored(plan.run_id, question.qid) and not self.retry_errors:
                    skipped_errors += 1
                    continue
            attempted += 1
            started = time.perf_counter()
            try:
                result = self.executor(plan, question)
                metrics = evaluate_result(result, question)
                metrics.setdefault("seconds", round(time.perf_counter() - started, 3))
                meta = {"status": "ok", **(result.get("_meta") or {})}
                self.store.add_metrics(plan.run_id, question.qid, metrics, meta=meta)
                status = "ok"
            except Exception as exc:  # noqa: BLE001 - failures are data
                errors += 1
                self.store.add_metric(plan.run_id, question.qid, "error", 1.0,
                                      meta={"type": type(exc).__name__, "message": str(exc)[:500]})
                status = "error"
            if self.log:
                self.log({"run_id": plan.run_id, "qid": question.qid, "status": status})
        has_failures = errors > 0 or skipped_errors > 0
        self.store.set_status(plan.run_id, "complete_with_errors" if has_failures else "complete")
        return {"run_id": plan.run_id, "attempted": attempted, "skipped": completed,
                "skipped_errors": skipped_errors, "errors": errors}

    def run(self, spec: Spec, plans: Iterable[RunPlan], questions: Sequence[Question] | None = None) -> list[dict[str, Any]]:
        explicit = list(questions) if questions is not None else None
        results: list[dict[str, Any]] = []
        for plan in plans:
            selected = explicit if explicit is not None else load_questions(
                spec, limit=self.limit, dataset=plan.dataset)
            results.append(self.run_plan(plan, selected))
        return results


def default_executor(plan: RunPlan, question: Question) -> Mapping[str, Any]:
    """Use the real runtime.  R0 is rejected by the guard until modules exist."""
    machine = lab_runtime.Runtime(plan.effective_config)
    return machine.answer(question.sample_id, question.qa["question"])


def make_executor(name: str = "legacy", *, offline: bool = False):
    """Factory used by the CLI: ``legacy`` (Runtime) or ``e2e`` (module pipeline)."""
    if name == "e2e":
        from .executor import make_e2e_executor

        return make_e2e_executor(offline=offline)
    if name in ("legacy", "default"):
        return None
    raise ValueError(f"unknown executor: {name!r}; expected legacy or e2e")
