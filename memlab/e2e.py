"""End-to-end S4 pipeline: retrieve -> merge -> use.

``E2EPipeline`` is deliberately thin: W/S are built once into the context's store,
R returns a :class:`~memlab.retrieve.RetrievalResult`, M returns the merged context
and U returns an :class:`~memlab.use.AnswerResult`.  Keeping the orchestrator thin
means M and U candidates can be compared on the same retrieval result.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Sequence

from .merge import MergePipeline, MergeResult
from .retrieve import RetrievalResult, RetrievalRunner
from .use import AnswerResult, UsePipeline


@dataclass
class E2EResult:
    query: str
    retrieval: RetrievalResult
    merge: MergeResult
    answer: AnswerResult
    trace: list[dict]
    tokens: int
    latency_ms: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "candidates": [candidate.memory_id for candidate in self.merge.candidates],
            "answer": self.answer.as_dict(),
            "tokens": self.tokens,
            "latency_ms": self.latency_ms,
            "trace": list(self.trace),
            "merge": self.merge.as_dict(),
        }


class E2EPipeline:
    def __init__(self, ctx: Any, *, runner: RetrievalRunner | None = None,
                 merger: MergePipeline | None = None, user: UsePipeline | None = None):
        self.ctx = ctx
        self.runner = runner or RetrievalRunner()
        self.merger = merger or MergePipeline.from_config(ctx)
        self.user = user or UsePipeline.from_config(ctx)

    def run(self, query: str, *, k: int | None = None,
            gold_turns: Sequence[str] | None = None) -> E2EResult:
        started = time.perf_counter()
        retrieval = self.runner.run(query, self.ctx, k)
        merged = self.merger.run(retrieval, self.ctx.store, self.ctx, gold_turns=gold_turns)
        answer = self.user.run(query, merged, retrieval.frame, self.ctx.store, self.ctx)
        latency = round((time.perf_counter() - started) * 1000, 3)
        trace = list(retrieval.trace) + list(merged.trace) + list(answer.trace)
        trace.append({"stage": "e2e", "name": "complete",
                      "detail": f"{len(merged.candidates)} candidates, {answer.answer[:40]!r}", "ms": latency})
        return E2EResult(query=query, retrieval=retrieval, merge=merged, answer=answer,
                         trace=trace, tokens=answer.tokens, latency_ms=latency)
