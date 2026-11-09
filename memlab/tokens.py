"""Cheap token estimation shared by the M/U stages.

These are estimates for waterfall bookkeeping, not billing.  4 characters per token
is the usual English rule of thumb; named entities and dates are tokenised more
coarsely by the real model, so the estimate is only used to compare stages.
"""
from __future__ import annotations

import math
from typing import Iterable


def estimate_tokens(text: object) -> int:
    value = "" if text is None else str(text)
    if not value:
        return 0
    return max(1, math.ceil(len(value) / 4))


def estimate_many(texts: Iterable[object]) -> int:
    return sum(estimate_tokens(text) for text in texts)
