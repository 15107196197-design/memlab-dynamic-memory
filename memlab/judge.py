"""LLM-as-Judge for B-level answer scoring.

The judge is deliberately small and separate from the answerer: it receives the
question, gold answer and candidate answer, and returns binary correctness /
faithfulness plus a short reason.  It uses the same provider adapter as the answer
LLM, so Ollama and OpenAI-compatible endpoints share one path.
"""
from __future__ import annotations

from typing import Any, Mapping

from .llm import LLMClient

JUDGE_PROMPT = """You are a strict evaluator for a memory QA system.
Decide whether the candidate answer is correct with respect to the gold answer,
and whether it is faithful to the evidence. Do not reward verbosity.
Return only JSON:
{{"correct": true|false, "faithful": true|false, "confidence": 0.0-1.0, "reason": "<= 20 words"}}

Question: {question}
Gold answer: {gold}
Candidate answer: {answer}
Evidence: {evidence}
"""


class Judge:
    def __init__(self, llm: LLMClient, *, name: str = "llm_judge"):
        self.llm = llm
        self.name = name

    @classmethod
    def from_environment(cls, environment: Mapping[str, Any] | None) -> "Judge":
        env = dict(environment or {})
        block = env.get("judge") if isinstance(env.get("judge"), Mapping) else env.get("llm")
        if not isinstance(block, Mapping):
            block = {}
        return cls(LLMClient.from_environment(block))

    def score(self, question: str, gold: Any, answer: Any,
              evidence: str = "") -> dict[str, Any]:
        prompt = JUDGE_PROMPT.format(
            question=question, gold=gold, answer=answer,
            evidence=(evidence or "")[:4000],
        )
        result = self.llm.generate(prompt, json_mode=True, max_tokens=160)
        if not isinstance(result, Mapping):
            raise ValueError(f"judge returned non-object: {type(result).__name__}")
        correct = bool(result.get("correct", False))
        faithful = bool(result.get("faithful", False))
        try:
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "judge_correct": int(correct),
            "judge_faithful": int(faithful),
            "judge_confidence": confidence,
            "judge_model": getattr(self.llm, "effective_model", None) or "",
            "judge_reason": str(result.get("reason", ""))[:200],
        }
