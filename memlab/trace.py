"""Small stage trace shared by the W/S/R modules.

A trace is a list of ``{stage, name, detail, ms}`` steps.  It is deliberately
plain data: the runner, CLI and Web can serialise it without knowing the module.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TraceStep:
    stage: str
    name: str
    detail: str
    ms: float


class Trace:
    """Records steps and the time elapsed since the previous step."""

    def __init__(self):
        self.steps: list[TraceStep] = []
        self._last = time.perf_counter()

    def add(self, stage: str, name: str, detail: str = "") -> TraceStep:
        now = time.perf_counter()
        step = TraceStep(stage=stage, name=name, detail=detail, ms=round((now - self._last) * 1000, 3))
        self.steps.append(step)
        self._last = now
        return step

    def to_list(self) -> list[dict]:
        return [asdict(step) for step in self.steps]

    def __len__(self) -> int:
        return len(self.steps)
