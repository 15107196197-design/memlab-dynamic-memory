"""Legacy (B0) method adapters.

The four original methods become registry entries on the ``method`` axis without
changing their behaviour: each adapter forwards to :func:`memwb.pipeline.answer`
with the same method name and parameters.  A1 acceptance is "the 10-question
output is identical to the pre-``memlab`` code", so nothing here may normalise,
re-rank or post-process the pipeline result.
"""
from __future__ import annotations

from typing import Any

from memwb import extraction, pipeline

from .registry import register

AXIS = "method"

# Prompt set that identifies the legacy pipeline.  A manifest hashes this, so a
# prompt edit invalidates runs even before S2 introduces per-stage prompt registries.
PROMPTS: dict[str, str] = {
    "extract": extraction.PROMPT,
    "state": pipeline.STATE_PROMPT,
    "review": pipeline.REVIEW_PROMPT,
    "answer": pipeline.ANSWER_PROMPT,
    "baseline": pipeline.BASELINE_PROMPT,
}

LEGACY_METHODS: dict[str, str] = {
    "legacy_full": "full",
    "legacy_vector": "vector",
    "legacy_hybrid": "hybrid",
    "legacy_dynamic": "dynamic",
}


class LegacyAdapter:
    """Shared forwarding logic; subclasses only fix the pipeline method name."""

    axis = AXIS
    name = ""
    method = ""
    params_allowed = frozenset({"k", "expand", "as_of"})

    def __init__(self, k: int = 15, expand: int = 8, as_of: str | None = None):
        self.k = k
        self.expand = expand
        self.as_of = as_of

    @classmethod
    def validate_params(cls, params: dict[str, Any]) -> None:
        unknown = set(params) - cls.params_allowed
        if unknown:
            raise TypeError(
                f"{cls.axis}:{cls.name} does not accept {sorted(unknown)}; "
                f"allowed={sorted(cls.params_allowed)}"
            )

    def answer(self, sample_id: str, question: str, *, k: int | None = None,
               as_of: str | None = None, expand: int | None = None) -> dict[str, Any]:
        """Return exactly what the legacy pipeline returns."""
        return pipeline.answer(
            sample_id,
            question,
            self.method,
            k=self.k if k is None else k,
            as_of=self.as_of if as_of is None else as_of,
            expand=self.expand if expand is None else expand,
        )


@register(AXIS, "legacy_full")
class LegacyFull(LegacyAdapter):
    method = "full"


@register(AXIS, "legacy_vector")
class LegacyVector(LegacyAdapter):
    method = "vector"


@register(AXIS, "legacy_hybrid")
class LegacyHybrid(LegacyAdapter):
    method = "hybrid"


@register(AXIS, "legacy_dynamic")
class LegacyDynamic(LegacyAdapter):
    method = "dynamic"
