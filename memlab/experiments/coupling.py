"""E2 coupling analysis: quality propagation, conversion and attribution.

S7a builds the analysis layer *before* S6 finishes.  It reads the same SQLite rows
as S5, so synthetic fixtures can test the math without a model; S7b then points it
at real S6 runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .store import ResultStore


@dataclass(frozen=True)
class Conversion:
    run_id: str
    gate: str
    gate_min: float
    outcome: str
    outcome_min: float
    n_total: int
    n_gated: int
    n_success: int
    conversion: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "gate": self.gate,
            "gate_min": self.gate_min,
            "outcome": self.outcome,
            "outcome_min": self.outcome_min,
            "n_total": self.n_total,
            "n_gated": self.n_gated,
            "n_success": self.n_success,
            "conversion": self.conversion,
        }


def _by_question(store: ResultStore, run_id: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for row in store.metrics(run_id=run_id):
        if row.get("value") is None:
            continue
        out.setdefault(str(row["qid"]), {})[str(row["metric"])] = float(row["value"])
    return out


def conversion(store: ResultStore, run_id: str, *, gate: str = "evidence_recall",
               gate_min: float = 1.0, outcome: str = "answer_f1",
               outcome_min: float = 0.0) -> Conversion:
    """P(outcome above threshold | gate above threshold) for one run.

    ``n_gated`` is the denominator, not all questions: the question is conditional.
    """
    values = _by_question(store, run_id)
    gated = [q for q, metrics in values.items() if metrics.get(gate) is not None and metrics[gate] >= gate_min]
    success = [q for q in gated if values[q].get(outcome) is not None and values[q][outcome] > outcome_min]
    return Conversion(
        run_id=run_id, gate=gate, gate_min=gate_min, outcome=outcome,
        outcome_min=outcome_min, n_total=len(values), n_gated=len(gated),
        n_success=len(success),
        conversion=round(len(success) / len(gated), 4) if gated else None,
    )


def conversion_table(store: ResultStore, *, gate: str = "evidence_recall",
                     gate_min: float = 1.0, outcome: str = "answer_f1") -> list[dict[str, Any]]:
    return [conversion(store, row["run_id"], gate=gate, gate_min=gate_min, outcome=outcome).to_dict()
            for row in store.runs()]


def _mean(store: ResultStore, run_id: str, metric: str) -> float | None:
    values = [float(row["value"]) for row in store.metrics(run_id=run_id, metric=metric)
              if row.get("value") is not None]
    return sum(values) / len(values) if values else None


def oracle_gap(store: ResultStore, system_run: str, oracle_run: str,
               metric: str = "answer_f1") -> dict[str, Any]:
    system = _mean(store, system_run, metric)
    oracle = _mean(store, oracle_run, metric)
    gap = None if system is None or oracle is None else round(oracle - system, 4)
    return {
        "metric": metric, "system_run": system_run, "oracle_run": oracle_run,
        "system": round(system, 4) if system is not None else None,
        "oracle": round(oracle, 4) if oracle is not None else None,
        "gap": gap,
    }


def _run_meta(store: ResultStore, run_id: str) -> dict[str, Any]:
    run = store.get_run(run_id) or {}
    factors = run.get("factors") or {}
    environment = run.get("environment") or {}
    return {"factors": factors, "environment": environment}


def group_metric(store: ResultStore, metric: str, *, factor: str = "module") -> list[dict[str, Any]]:
    """Group run means by a factor (run.factors[factor])."""
    groups: dict[str, list[float]] = {}
    for row in store.runs():
        meta = _run_meta(store, row["run_id"])
        key = meta["factors"].get(factor)
        if key is None:
            key = "unknown"
        value = _mean(store, row["run_id"], metric)
        if value is not None:
            groups.setdefault(str(key), []).append(value)
    return [{"group": key, "n": len(values), "mean": round(sum(values) / len(values), 4)}
            for key, values in sorted(groups.items())]


def eta_squared(groups: Sequence[Sequence[float]]) -> float | None:
    """One-way effect size; a cheap screen, not a replacement for LMM."""
    flat = [value for group in groups for value in group]
    if len(flat) < 2:
        return None
    overall = sum(flat) / len(flat)
    between = sum(len(group) * (sum(group) / len(group) - overall) ** 2 for group in groups if group)
    total = sum((value - overall) ** 2 for value in flat)
    return round(between / total, 4) if total else None


def llm_attribution(store: ResultStore, metric: str = "answer_f1") -> list[dict[str, Any]]:
    """Run means grouped by the configured LLM model/tier, for the LLM confound."""
    groups: dict[str, list[float]] = {}
    for row in store.runs():
        meta = _run_meta(store, row["run_id"])
        env = meta["environment"]
        llm = env.get("llm") if isinstance(env.get("llm"), Mapping) else {}
        key = str(llm.get("model") or env.get("llm_level") or "unknown")
        value = _mean(store, row["run_id"], metric)
        if value is not None:
            groups.setdefault(key, []).append(value)
    return [{"llm": key, "n": len(values), "mean": round(sum(values) / len(values), 4)}
            for key, values in sorted(groups.items())]


def bottleneck(store: ResultStore, run_id: str, *,
               gate: str = "evidence_recall", outcome: str = "answer_f1") -> dict[str, Any]:
    """Small diagnostic: is the gate or the use stage the likely bottleneck?"""
    conv = conversion(store, run_id, gate=gate, outcome=outcome)
    gate_mean = _mean(store, run_id, gate)
    outcome_mean = _mean(store, run_id, outcome)
    if conv.n_gated == 0:
        diagnosis = "no_gated_questions"
    elif conv.conversion is not None and conv.conversion < 0.5:
        diagnosis = "use_or_merge_bottleneck"
    elif gate_mean is not None and gate_mean < 0.5:
        diagnosis = "retrieval_bottleneck"
    else:
        diagnosis = "no_clear_bottleneck"
    return {
        "run_id": run_id, "gate_mean": gate_mean, "outcome_mean": outcome_mean,
        "conversion": conv.to_dict(), "diagnosis": diagnosis,
    }
